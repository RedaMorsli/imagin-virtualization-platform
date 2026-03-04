import base64
import os
import re
import tempfile
import time
from typing import Any
from urllib.error import HTTPError as UrlHTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

import yaml
from kubernetes import client, config, utils
from kubernetes.config import kube_config
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError, MaxRetryError

HEADLAMP_MANIFEST_URL = "https://raw.githubusercontent.com/kubernetes-sigs/headlamp/main/kubernetes-headlamp.yaml"
HEADLAMP_SERVICE_NAME = "headlamp"
HEADLAMP_DEPLOYMENT_NAME = "headlamp"
HEADLAMP_SERVICE_NAMESPACE = "kube-system"
HEADLAMP_NODE_PORT = 30080
HEADLAMP_ADMIN_SERVICE_ACCOUNT = "headlamp-admin"
HEADLAMP_ADMIN_CLUSTER_ROLE_BINDING = "headlamp-admin"
HEADLAMP_ADMIN_CLUSTER_ROLE = "cluster-admin"
HEADLAMP_TOKEN_REQUEST_AUDIENCE = "https://kubernetes.default.svc"
K8S_API_REWRITE_HOST_ENV = "K8S_API_REWRITE_HOST"


def _configured_kube_api_rewrite_host() -> str | None:
    rewrite_host = os.environ.get(K8S_API_REWRITE_HOST_ENV, "").strip()
    if not rewrite_host:
        return None
    return rewrite_host


def _load_kube_config(context: str) -> None:
    rewrite_host = _configured_kube_api_rewrite_host()
    if not rewrite_host:
        config.load_kube_config(context=context)
        return

    try:
        rewritten_kubeconfig = get_raw_kubeconfig(context=context, rewrite_host=rewrite_host)
    except RuntimeError as exc:
        raise ConfigException(str(exc)) from exc

    temp_kubeconfig_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as temp_kubeconfig:
            temp_kubeconfig.write(rewritten_kubeconfig)
            temp_kubeconfig_path = temp_kubeconfig.name
        config.load_kube_config(config_file=temp_kubeconfig_path, context=context)
    finally:
        if temp_kubeconfig_path:
            try:
                os.remove(temp_kubeconfig_path)
            except OSError:
                pass


def apply_manifest(context: str, manifest_dict: dict) -> None:
    if not context:
        raise ValueError("context is required")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    k8s_client = client.ApiClient()

    try:
        utils.create_from_dict(k8s_client, manifest_dict)
    except utils.FailToCreateError as exc:
        raise RuntimeError("failed to apply manifest to cluster") from exc
    except client.ApiException as exc:
        raise RuntimeError("failed to apply manifest to cluster") from exc


def apply_manifest_from_url(context: str, manifest_url: str) -> None:
    if not context:
        raise ValueError("context is required")
    if not manifest_url:
        raise ValueError("manifest_url is required")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    k8s_client = client.ApiClient()

    # Prefer native YAML apply path in case the installed kubernetes client supports URL inputs.
    try:
        utils.create_from_yaml(k8s_client, manifest_url)
        return
    except (utils.FailToCreateError, client.ApiException) as exc:
        raise RuntimeError("failed to apply manifest to cluster") from exc
    except (FileNotFoundError, OSError, TypeError, ValueError):
        pass

    try:
        with urlopen(manifest_url, timeout=30) as response:
            manifest_content = response.read().decode("utf-8")
    except (UrlHTTPError, URLError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"failed to download manifest from '{manifest_url}'") from exc

    manifests = [doc for doc in yaml.safe_load_all(manifest_content) if doc]
    if not manifests:
        raise RuntimeError("manifest URL did not contain any Kubernetes resources")

    try:
        for manifest in manifests:
            utils.create_from_dict(k8s_client, manifest)
    except (utils.FailToCreateError, client.ApiException) as exc:
        raise RuntimeError("failed to apply manifest to cluster") from exc


def _normalize_base_url_path(base_url: str) -> str:
    normalized = (base_url or "").strip()
    if not normalized:
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    normalized = re.sub(r"/{2,}", "/", normalized)
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def _build_probe_http_get_patch(probe: Any, base_url_path: str) -> dict | None:
    if probe is None:
        return None

    http_get = getattr(probe, "http_get", None)
    if http_get is None:
        return None

    http_get_patch = {
        "path": base_url_path,
        "port": http_get.port,
    }
    if http_get.host:
        http_get_patch["host"] = http_get.host
    if http_get.scheme:
        http_get_patch["scheme"] = http_get.scheme

    headers = []
    for header in (http_get.http_headers or []):
        if not header or not getattr(header, "name", None):
            continue
        headers.append({"name": header.name, "value": getattr(header, "value", "")})
    if headers:
        http_get_patch["httpHeaders"] = headers

    return {"httpGet": http_get_patch}


def configure_headlamp_base_url(context: str, base_url: str) -> None:
    if not context:
        raise ValueError("context is required")

    normalized_base_url = _normalize_base_url_path(base_url)

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    apps_api = client.AppsV1Api()
    try:
        deployment = apps_api.read_namespaced_deployment(
            name=HEADLAMP_DEPLOYMENT_NAME,
            namespace=HEADLAMP_SERVICE_NAMESPACE,
        )
    except client.ApiException as exc:
        if exc.status == 404:
            raise ValueError(
                f"deployment '{HEADLAMP_DEPLOYMENT_NAME}' not found in namespace "
                f"'{HEADLAMP_SERVICE_NAMESPACE}'"
            ) from exc
        raise RuntimeError("failed to read headlamp deployment from cluster") from exc

    pod_spec = getattr(getattr(deployment.spec, "template", None), "spec", None)
    containers = list(getattr(pod_spec, "containers", []) or [])
    if not containers:
        raise RuntimeError("headlamp deployment has no containers")

    target_container = next(
        (container for container in containers if container.name == HEADLAMP_SERVICE_NAME),
        containers[0],
    )

    original_args = list(target_container.args or [])
    updated_args: list[str] = []
    skip_next = False
    for arg in original_args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--base-url":
            skip_next = True
            continue
        if isinstance(arg, str) and arg.startswith("--base-url="):
            continue
        updated_args.append(arg)
    updated_args.append(f"--base-url={normalized_base_url}")

    container_patch: dict[str, Any] = {
        "name": target_container.name,
        "args": updated_args,
    }

    for probe_attr, patch_key in (
        ("liveness_probe", "livenessProbe"),
        ("readiness_probe", "readinessProbe"),
        ("startup_probe", "startupProbe"),
    ):
        probe_patch = _build_probe_http_get_patch(
            getattr(target_container, probe_attr, None),
            normalized_base_url,
        )
        if probe_patch is not None:
            container_patch[patch_key] = probe_patch

    patch_body = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [container_patch],
                }
            }
        }
    }

    try:
        apps_api.patch_namespaced_deployment(
            name=HEADLAMP_DEPLOYMENT_NAME,
            namespace=HEADLAMP_SERVICE_NAMESPACE,
            body=patch_body,
        )
    except client.ApiException as exc:
        raise RuntimeError(
            f"failed to set Headlamp base URL to '{normalized_base_url}' for context '{context}'"
        ) from exc


def change_service_type(
    context: str,
    service_name: str,
    namespace: str,
    service_type: str,
    node_port: int | None = None,
) -> None:
    if not context:
        raise ValueError("context is required")
    if not service_name:
        raise ValueError("service_name is required")
    if not namespace:
        raise ValueError("namespace is required")
    if not service_type:
        raise ValueError("service_type is required")

    normalized_type = service_type.strip().lower()
    if normalized_type == "clusterip":
        target_type = "ClusterIP"
    elif normalized_type == "nodeport":
        target_type = "NodePort"
    else:
        raise ValueError("service_type must be either 'ClusterIP' or 'NodePort'")

    parsed_node_port = None
    if node_port is not None:
        try:
            parsed_node_port = int(node_port)
        except (TypeError, ValueError):
            raise ValueError("node_port must be an integer") from None
        if parsed_node_port < 1 or parsed_node_port > 65535:
            raise ValueError("node_port must be between 1 and 65535")

    if target_type != "NodePort" and parsed_node_port is not None:
        raise ValueError("node_port can only be set when service_type is 'NodePort'")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    core_api = client.CoreV1Api()
    try:
        svc = core_api.read_namespaced_service(service_name, namespace)
    except client.ApiException as exc:
        if exc.status == 404:
            raise ValueError(f"service '{service_name}' not found in namespace '{namespace}'") from exc
        raise RuntimeError("failed to read service from cluster") from exc

    svc_ports = svc.spec.ports or []
    if not svc_ports:
        raise RuntimeError(f"service '{service_name}' has no ports")

    patch_ports = []
    for i, svc_port in enumerate(svc_ports):
        port_patch = {
            "port": svc_port.port,
            "protocol": svc_port.protocol or "TCP",
            "targetPort": svc_port.target_port,
        }
        if svc_port.name:
            port_patch["name"] = svc_port.name
        if svc_port.app_protocol:
            port_patch["appProtocol"] = svc_port.app_protocol

        if target_type == "NodePort":
            if parsed_node_port is not None and i == 0:
                port_patch["nodePort"] = parsed_node_port
            elif svc_port.node_port is not None:
                port_patch["nodePort"] = svc_port.node_port
        else:
            port_patch["nodePort"] = None

        patch_ports.append(port_patch)

    patch_body = {
        "spec": {
            "type": target_type,
            "ports": patch_ports,
        }
    }

    try:
        core_api.patch_namespaced_service(service_name, namespace, patch_body)
    except client.ApiException as exc:
        raise RuntimeError(
            f"failed to change service '{service_name}' in namespace '{namespace}' to '{target_type}'"
        ) from exc


def install_headlamp(
    context: str,
    node_port: int = HEADLAMP_NODE_PORT,
    base_url: str = "/",
) -> None:
    apply_manifest_from_url(context, HEADLAMP_MANIFEST_URL)
    change_service_type(
        context=context,
        service_name=HEADLAMP_SERVICE_NAME,
        namespace=HEADLAMP_SERVICE_NAMESPACE,
        service_type="NodePort",
        node_port=node_port,
    )
    configure_headlamp_base_url(context=context, base_url=base_url)


def ensure_service_account(context: str, namespace: str, service_account_name: str) -> None:
    if not context:
        raise ValueError("context is required")
    if not namespace:
        raise ValueError("namespace is required")
    if not service_account_name:
        raise ValueError("service_account_name is required")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    core_api = client.CoreV1Api()
    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(name=service_account_name, namespace=namespace)
    )

    try:
        core_api.create_namespaced_service_account(namespace=namespace, body=service_account)
    except client.ApiException as exc:
        if exc.status != 409:
            raise RuntimeError(
                f"failed to create service account '{service_account_name}' in namespace '{namespace}'"
            ) from exc


def ensure_cluster_role_binding(
    context: str,
    binding_name: str,
    service_account_name: str,
    namespace: str,
    cluster_role_name: str = HEADLAMP_ADMIN_CLUSTER_ROLE,
) -> None:
    if not context:
        raise ValueError("context is required")
    if not binding_name:
        raise ValueError("binding_name is required")
    if not service_account_name:
        raise ValueError("service_account_name is required")
    if not namespace:
        raise ValueError("namespace is required")
    if not cluster_role_name:
        raise ValueError("cluster_role_name is required")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    rbac_api = client.RbacAuthorizationV1Api()
    binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {"name": binding_name},
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": cluster_role_name,
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": service_account_name,
                "namespace": namespace,
            }
        ],
    }

    try:
        rbac_api.create_cluster_role_binding(body=binding)
    except client.ApiException as exc:
        if exc.status != 409:
            raise RuntimeError(f"failed to create cluster role binding '{binding_name}'") from exc


def _create_service_account_token_legacy(
    core_api: client.CoreV1Api,
    namespace: str,
    service_account_name: str,
) -> str:
    secret_name = f"{service_account_name}-token"
    token_secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=secret_name,
            namespace=namespace,
            annotations={"kubernetes.io/service-account.name": service_account_name},
        ),
        type="kubernetes.io/service-account-token",
    )

    try:
        core_api.create_namespaced_secret(namespace=namespace, body=token_secret)
    except client.ApiException as exc:
        if exc.status != 409:
            raise RuntimeError(
                f"failed to create token secret '{secret_name}' in namespace '{namespace}'"
            ) from exc

    for _ in range(30):
        try:
            secret = core_api.read_namespaced_secret(name=secret_name, namespace=namespace)
        except client.ApiException as exc:
            if exc.status == 404:
                time.sleep(1)
                continue
            raise RuntimeError(
                f"failed to read token secret '{secret_name}' in namespace '{namespace}'"
            ) from exc

        encoded_token = (secret.data or {}).get("token")
        if encoded_token:
            try:
                return base64.b64decode(encoded_token).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError(f"failed to decode token from secret '{secret_name}'") from exc

        time.sleep(1)

    raise RuntimeError(f"timed out waiting for token secret '{secret_name}' to be populated")


def create_service_account_token(
    context: str,
    namespace: str,
    service_account_name: str,
    expiration_seconds: int | None = None,
) -> str:
    if not context:
        raise ValueError("context is required")
    if not namespace:
        raise ValueError("namespace is required")
    if not service_account_name:
        raise ValueError("service_account_name is required")
    if expiration_seconds is not None:
        try:
            expiration_seconds = int(expiration_seconds)
        except (TypeError, ValueError):
            raise ValueError("expiration_seconds must be an integer") from None
        if expiration_seconds < 1:
            raise ValueError("expiration_seconds must be at least 1")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    def _extract_token(token_response: Any) -> str | None:
        status_obj = getattr(token_response, "status", None)
        token_value = getattr(status_obj, "token", None) if status_obj is not None else None
        if token_value:
            return token_value

        if isinstance(token_response, dict):
            token_value = (token_response.get("status") or {}).get("token")
            if isinstance(token_value, str) and token_value:
                return token_value

        return None

    core_api = client.CoreV1Api()
    token_request_error = None
    create_token_method = getattr(core_api, "create_namespaced_service_account_token", None)

    if callable(create_token_method):
        base_spec = {}
        if expiration_seconds is not None:
            base_spec["expirationSeconds"] = expiration_seconds

        token_request_bodies = [{"spec": dict(base_spec)}]
        token_request_with_audience = {"spec": dict(base_spec)}
        token_request_with_audience["spec"]["audiences"] = [HEADLAMP_TOKEN_REQUEST_AUDIENCE]
        token_request_bodies.append(token_request_with_audience)

        for token_request_body in token_request_bodies:
            try:
                token_response = create_token_method(
                    name=service_account_name,
                    namespace=namespace,
                    body=token_request_body,
                )
            except TypeError:
                try:
                    token_response = create_token_method(
                        service_account_name,
                        namespace,
                        token_request_body,
                    )
                except (client.ApiException, TypeError, ValueError) as exc:
                    token_request_error = exc
                    continue
            except (client.ApiException, ValueError) as exc:
                token_request_error = exc
                continue

            token = _extract_token(token_response)
            if token:
                return token
            token_request_error = RuntimeError(
                "TokenRequest API returned an empty token in response"
            )

    try:
        return _create_service_account_token_legacy(
            core_api=core_api,
            namespace=namespace,
            service_account_name=service_account_name,
        )
    except Exception as legacy_exc:
        if token_request_error is not None:
            raise RuntimeError(
                f"failed to create service account token via TokenRequest and legacy fallback: {token_request_error}"
            ) from legacy_exc
        raise


def create_headlamp_service_account_token(context: str) -> str:
    ensure_service_account(
        context=context,
        namespace=HEADLAMP_SERVICE_NAMESPACE,
        service_account_name=HEADLAMP_ADMIN_SERVICE_ACCOUNT,
    )
    ensure_cluster_role_binding(
        context=context,
        binding_name=HEADLAMP_ADMIN_CLUSTER_ROLE_BINDING,
        service_account_name=HEADLAMP_ADMIN_SERVICE_ACCOUNT,
        namespace=HEADLAMP_SERVICE_NAMESPACE,
        cluster_role_name=HEADLAMP_ADMIN_CLUSTER_ROLE,
    )
    return create_service_account_token(
        context=context,
        namespace=HEADLAMP_SERVICE_NAMESPACE,
        service_account_name=HEADLAMP_ADMIN_SERVICE_ACCOUNT,
    )


def get_raw_kubeconfig(context: str | None = None, rewrite_host: str | None = None) -> str:
    kubeconfig_path = os.environ.get("KUBECONFIG", kube_config.KUBE_CONFIG_DEFAULT_LOCATION)
    merger = kube_config.KubeConfigMerger(kubeconfig_path)
    config_node = merger.config

    if config_node is None:
        raise RuntimeError(f"failed to load kubeconfig from '{kubeconfig_path}'")

    if context:
        try:
            kube_config.KubeConfigLoader(config_node, active_context=context)
        except ConfigException as exc:
            raise RuntimeError(f"failed to use context '{context}' from kubeconfig") from exc

    def _strip_config_nodes(value):
        if isinstance(value, kube_config.ConfigNode):
            return _strip_config_nodes(value.value)
        if isinstance(value, list):
            return [_strip_config_nodes(item) for item in value]
        if isinstance(value, dict):
            return {key: _strip_config_nodes(val) for key, val in value.items()}
        return value

    def _rewrite_cluster_servers(config_dict: dict):
        clusters = config_dict.get("clusters", [])
        if not isinstance(clusters, list):
            return
        for cluster in clusters:
            cluster_spec = cluster.get("cluster") if isinstance(cluster, dict) else None
            if not isinstance(cluster_spec, dict):
                continue
            server = cluster_spec.get("server")
            if not isinstance(server, str):
                continue
            parsed = urlparse(server)
            if not parsed.scheme or not parsed.netloc:
                continue
            original_host = parsed.hostname
            new_netloc = f"{rewrite_host}"
            if parsed.port:
                new_netloc = f"{new_netloc}:{parsed.port}"
            cluster_spec["server"] = urlunparse(parsed._replace(netloc=new_netloc))
            # Keep TLS verification bound to the original API server certificate identity.
            if (
                original_host
                and rewrite_host != original_host
                and not cluster_spec.get("tls-server-name")
            ):
                cluster_spec["tls-server-name"] = original_host

    sanitized_config = _strip_config_nodes(config_node)
    if context:
        def _filter_for_context(config_dict: dict, context_name: str) -> dict:
            contexts = config_dict.get("contexts") or []
            match = next((c for c in contexts if c.get("name") == context_name), None)
            if not match:
                raise RuntimeError(f"context '{context_name}' not found in kubeconfig")

            match_ctx = match.get("context", {})
            cluster_name = match_ctx.get("cluster")
            user_name = match_ctx.get("user")

            config_dict["contexts"] = [match]
            config_dict["current-context"] = context_name

            if cluster_name:
                config_dict["clusters"] = [
                    c for c in (config_dict.get("clusters") or []) if c.get("name") == cluster_name
                ]
            if user_name:
                config_dict["users"] = [
                    u for u in (config_dict.get("users") or []) if u.get("name") == user_name
                ]
            return config_dict

        sanitized_config = _filter_for_context(sanitized_config, context)
    if rewrite_host:
        _rewrite_cluster_servers(sanitized_config)

    return yaml.safe_dump(sanitized_config, sort_keys=False)


def get_cluster_status(context: str) -> dict:
    if not context:
        raise ValueError("context is required")

    try:
        _load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    core_api = client.CoreV1Api()
    try:
        nodes = core_api.list_node().items
    except (MaxRetryError, Urllib3HTTPError):
        # Cluster is unreachable (e.g., stopped); surface a graceful status instead of raising.
        return {"nodes_ready": 0, "error": "cluster unreachable"}
    except client.ApiException as exc:
        raise RuntimeError("failed to list nodes from cluster") from exc

    ready_nodes = 0
    for node in nodes:
        for condition in node.status.conditions or []:
            if condition.type == "Ready" and condition.status == "True":
                ready_nodes += 1
                break

    return {"nodes_ready": ready_nodes}
