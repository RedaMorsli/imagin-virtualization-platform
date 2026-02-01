import os
from urllib.parse import urlparse, urlunparse

import yaml
from kubernetes import client, config
from kubernetes.config import kube_config
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError, MaxRetryError


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
