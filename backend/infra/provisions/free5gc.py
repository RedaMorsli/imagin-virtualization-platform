"""
free5gc + UERANSIM + web console provisioner.

Deploys the towards5gs Helm charts (`towards5gs/free5gc` and optionally
`towards5gs/ueransim`) onto an existing K3D cluster, then exposes the free5gc
web console through Traefik.

Operational caveats:
    * Requires the `gtp5g` kernel module to be loaded on the Docker host running
      K3D. Linux only — does not work on Docker Desktop.
    * Requires Multus CNI in the cluster; auto-applied here if absent.
    * The helm CLI must be present in the backend container.

Provision config keys:
    namespace (str)               default "free5gc"
    deploy_ueransim (bool)        default True
    free5gc_chart_version (str)   default "1.1.7"
    ueransim_chart_version (str)  default "2.0.17"
    free5gc_values (dict)         optional helm values override
    ueransim_values (dict)        optional helm values override
    web_console (bool)            default True
    web_console_port (int)        default 30500 (NodePort exposed on the LB)

State persisted on the provision entry:
    namespace, deploy_ueransim, web_console_port,
    free5gc_chart_version, ueransim_chart_version,
    web_console: { endpoint_id, route_name, route_config_file, url, hostname, path_prefix } | None
"""

import os
import subprocess
import tempfile

import yaml
from kubernetes import client
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError, MaxRetryError

import infra.k8s as k8s
import infra.traefik as traefik

TOWARDS5GS_REPO_NAME = "towards5gs"
TOWARDS5GS_REPO_URL = "https://raw.githubusercontent.com/Orange-OpenSource/towards5gs-helm/main/repo/"
MULTUS_DAEMONSET_URL = (
    "https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/"
    "deployments/multus-daemonset.yml"
)
MULTUS_DAEMONSET_NAME = "kube-multus-ds"

DEFAULT_NAMESPACE = "free5gc"
DEFAULT_FREE5GC_CHART_VERSION = "1.1.7"
DEFAULT_UERANSIM_CHART_VERSION = "2.0.17"
DEFAULT_WEB_CONSOLE_PORT = 30500
WEBUI_SERVICE_NAME = "webui-service"

HELM_INSTALL_TIMEOUT = "10m"


def _run_helm_command(cmd: list[str], action: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{action} failed: {error_output}")
    return result


def _ensure_helm_repo() -> None:
    _run_helm_command(
        ["helm", "repo", "add", TOWARDS5GS_REPO_NAME, TOWARDS5GS_REPO_URL, "--force-update"],
        "helm repo add towards5gs",
    )
    _run_helm_command(["helm", "repo", "update", TOWARDS5GS_REPO_NAME], "helm repo update")


def _ensure_multus_installed(context: str) -> None:
    try:
        k8s._load_kube_config(context)
    except ConfigException as exc:
        raise RuntimeError(f"failed to load kubeconfig for context '{context}'") from exc

    apps_api = client.AppsV1Api()
    try:
        ds_list = apps_api.list_namespaced_daemon_set("kube-system")
    except client.ApiException as exc:
        raise RuntimeError("failed to list daemonsets in kube-system") from exc

    for ds in ds_list.items or []:
        if (ds.metadata.name or "").startswith("kube-multus") or ds.metadata.name == MULTUS_DAEMONSET_NAME:
            return

    k8s.apply_manifest_from_url(context, MULTUS_DAEMONSET_URL)


def _helm_install(
    context: str,
    release: str,
    chart: str,
    namespace: str,
    version: str | None,
    values_dict: dict | None,
) -> None:
    cmd = [
        "helm", "--kube-context", context,
        "upgrade", "--install", release, chart,
        "-n", namespace, "--create-namespace",
        "--wait", "--timeout", HELM_INSTALL_TIMEOUT,
    ]
    if version:
        cmd.extend(["--version", version])

    values_path = ""
    try:
        if values_dict:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False, encoding="utf-8"
            ) as tmp:
                yaml.safe_dump(values_dict, tmp, sort_keys=False)
                values_path = tmp.name
            cmd.extend(["-f", values_path])
        _run_helm_command(cmd, f"helm upgrade --install {release}")
    finally:
        if values_path:
            try:
                os.remove(values_path)
            except OSError:
                pass


def _helm_uninstall(context: str, release: str, namespace: str) -> None:
    result = subprocess.run(
        ["helm", "--kube-context", context, "uninstall", release, "-n", namespace, "--wait"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").lower()
        if "not found" in stderr or "release: not found" in stderr:
            return
        raise RuntimeError(
            f"helm uninstall {release} failed: {result.stderr.strip() or result.stdout.strip()}"
        )


def _seed_endpoint_id(provision_config: dict) -> str:
    seed = provision_config.get("_seed") or {}
    project_id = seed.get("project_id")
    infra_name = str(seed.get("infra_name") or "cluster").strip() or "cluster"
    return traefik.build_endpoint_id(f"free5gc-p{project_id}-{infra_name}")


def _resolve_port(provision_config: dict) -> int:
    raw_port = provision_config.get("web_console_port", DEFAULT_WEB_CONSOLE_PORT)
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        raise ValueError("free5gc 'web_console_port' must be an integer") from None
    if port < 30000 or port > 32767:
        raise ValueError("free5gc 'web_console_port' must be a valid NodePort (30000-32767)")
    return port


def pre_cluster_create(infra_config: dict, provision_config: dict) -> None:
    if provision_config.get("web_console", True) is not True:
        return
    port = _resolve_port(provision_config)
    provision_config["web_console_port"] = port
    ports = list(infra_config.get("ports") or [])
    if port not in ports:
        ports.append(port)
    infra_config["ports"] = ports


def provision(context: str, infra_config: dict, provision_config: dict) -> dict:
    if not context:
        raise ValueError("context is required")

    namespace = provision_config.get("namespace") or DEFAULT_NAMESPACE
    deploy_ueransim = provision_config.get("deploy_ueransim", True) is True
    free5gc_chart_version = provision_config.get("free5gc_chart_version") or DEFAULT_FREE5GC_CHART_VERSION
    ueransim_chart_version = provision_config.get("ueransim_chart_version") or DEFAULT_UERANSIM_CHART_VERSION
    free5gc_values = provision_config.get("free5gc_values") or None
    ueransim_values = provision_config.get("ueransim_values") or None
    expose_web_console = provision_config.get("web_console", True) is True

    _ensure_helm_repo()
    _ensure_multus_installed(context)

    _helm_install(
        context, "free5gc", "towards5gs/free5gc",
        namespace, free5gc_chart_version, free5gc_values,
    )

    if deploy_ueransim:
        _helm_install(
            context, "ueransim", "towards5gs/ueransim",
            namespace, ueransim_chart_version, ueransim_values,
        )

    web_console_state = None
    web_console_port = None
    if expose_web_console:
        web_console_port = _resolve_port(provision_config)
        k8s.change_service_type(
            context=context,
            service_name=WEBUI_SERVICE_NAME,
            namespace=namespace,
            service_type="NodePort",
            node_port=web_console_port,
        )
        endpoint_id = _seed_endpoint_id(provision_config)
        route = traefik.register_http_endpoint(route_name=endpoint_id, target_port=web_console_port)
        web_console_state = {
            "endpoint_id": route["endpoint_id"],
            "route_name": route["route_name"],
            "route_config_file": route["config_file"],
            "url": route["url"],
            "hostname": route["domain_name"],
            "path_prefix": route["path_prefix"],
        }

    return {
        "namespace": namespace,
        "deploy_ueransim": deploy_ueransim,
        "free5gc_chart_version": free5gc_chart_version,
        "ueransim_chart_version": ueransim_chart_version,
        "web_console_port": web_console_port,
        "web_console": web_console_state,
    }


def deprovision(context: str, infra_config: dict, provision_config: dict, provision_state: dict) -> None:
    state = provision_state or {}
    web_console = state.get("web_console")
    if web_console and web_console.get("endpoint_id"):
        try:
            traefik.delete_http_endpoint(web_console["endpoint_id"])
        except Exception as exc:
            print(f"warning: failed to delete free5gc Traefik route: {exc}")

    if not context:
        return

    namespace = state.get("namespace") or provision_config.get("namespace") or DEFAULT_NAMESPACE
    for release in ("ueransim", "free5gc"):
        try:
            _helm_uninstall(context, release, namespace)
        except Exception as exc:
            print(f"warning: helm uninstall {release} failed: {exc}")


def get_status(context: str, provision_config: dict, provision_state: dict) -> dict:
    state = provision_state or {}
    namespace = state.get("namespace") or provision_config.get("namespace") or DEFAULT_NAMESPACE
    web_console_url = (state.get("web_console") or {}).get("url")
    base = {
        "namespace": namespace,
        "core_ready": 0, "core_total": 0,
        "ran_ready": 0, "ran_total": 0,
        "web_console_url": web_console_url,
    }

    if not context:
        base["error"] = "context not set"
        return base

    try:
        k8s._load_kube_config(context)
    except ConfigException as exc:
        base["error"] = str(exc)
        return base

    core_api = client.CoreV1Api()
    try:
        pods = core_api.list_namespaced_pod(namespace).items
    except (MaxRetryError, Urllib3HTTPError):
        base["error"] = "cluster unreachable"
        return base
    except client.ApiException as exc:
        if exc.status == 404:
            base["error"] = "namespace not found"
            return base
        base["error"] = "api error"
        return base

    for pod in pods:
        labels = (pod.metadata.labels or {}) if pod.metadata else {}
        is_ran = labels.get("app") in ("gnb", "ue") or labels.get("component") in ("gnb", "ue")
        ready = False
        for cond in (pod.status.conditions or []) if pod.status else []:
            if cond.type == "Ready" and cond.status == "True":
                ready = True
                break
        if is_ran:
            base["ran_total"] += 1
            if ready:
                base["ran_ready"] += 1
        else:
            base["core_total"] += 1
            if ready:
                base["core_ready"] += 1
    return base


def reconcile(
    infra_id: int,
    project_id: int,
    infra_name: str,
    context: str,
    infra_config: dict,
    provision_config: dict,
    provision_state: dict,
) -> dict | None:
    state = dict(provision_state or {})
    if provision_config.get("web_console", True) is not True:
        return None
    if not state.get("web_console"):
        return None

    provision_config.setdefault("_seed", {"project_id": project_id, "infra_name": infra_name})
    endpoint_id = state["web_console"].get("endpoint_id") or _seed_endpoint_id(provision_config)
    port = state.get("web_console_port") or _resolve_port(provision_config)

    try:
        route = traefik.register_http_endpoint(route_name=endpoint_id, target_port=port)
    except Exception as exc:
        print(f"warning: failed to reconcile free5gc Traefik route for infra_id={infra_id}: {exc}")
        return None

    new_web_console = {
        "endpoint_id": route["endpoint_id"],
        "route_name": route["route_name"],
        "route_config_file": route["config_file"],
        "url": route["url"],
        "hostname": route["domain_name"],
        "path_prefix": route["path_prefix"],
    }
    if new_web_console == state.get("web_console"):
        return None
    state["web_console"] = new_web_console
    return state
