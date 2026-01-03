from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError, MaxRetryError


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
