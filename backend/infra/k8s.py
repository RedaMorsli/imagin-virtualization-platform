import os
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
HEADLAMP_SERVICE_NAMESPACE = "kube-system"
HEADLAMP_NODE_PORT = 30080


def apply_manifest(context: str, manifest_dict: dict) -> None:
    if not context:
        raise ValueError("context is required")

    try:
        config.load_kube_config(context=context)
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
        config.load_kube_config(context=context)
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
        config.load_kube_config(context=context)
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


def install_headlamp(context: str, node_port: int = HEADLAMP_NODE_PORT) -> None:
    apply_manifest_from_url(context, HEADLAMP_MANIFEST_URL)
    change_service_type(
        context=context,
        service_name=HEADLAMP_SERVICE_NAME,
        namespace=HEADLAMP_SERVICE_NAMESPACE,
        service_type="NodePort",
        node_port=node_port,
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
            new_netloc = f"{rewrite_host}"
            if parsed.port:
                new_netloc = f"{new_netloc}:{parsed.port}"
            cluster_spec["server"] = urlunparse(parsed._replace(netloc=new_netloc))

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
        config.load_kube_config(context=context)
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
