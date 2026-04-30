"""
Headlamp web UI provisioner.

Installs the upstream Headlamp manifest into the cluster's kube-system namespace,
exposes it on a NodePort matching the cluster's loadbalancer port mapping, and
publishes it through Traefik on the platform's domain.

Provision config keys:
    port (int, optional): NodePort the cluster's loadbalancer must forward.
                          Defaults to k8s.HEADLAMP_NODE_PORT (30080).

State persisted on the provision entry (filled in by `provision`):
    endpoint_id, route_name, route_config_file, url, hostname, path_prefix,
    port, token, service_account, service_account_namespace
"""

from kubernetes import client
from kubernetes.config.config_exception import ConfigException

import infra.k8s as k8s
import infra.traefik as traefik


def _seed_endpoint_id(provision_config: dict) -> str:
    seed = provision_config.get("_seed") or {}
    project_id = seed.get("project_id")
    infra_name = str(seed.get("infra_name") or "cluster").strip() or "cluster"
    return traefik.build_endpoint_id(f"headlamp-p{project_id}-{infra_name}")


def _resolve_port(provision_config: dict) -> int:
    raw_port = provision_config.get("port", k8s.HEADLAMP_NODE_PORT)
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        raise ValueError("headlamp 'port' must be an integer") from None
    if port < 1 or port > 65535:
        raise ValueError("headlamp 'port' must be between 1 and 65535")
    return port


def pre_cluster_create(infra_config: dict, provision_config: dict) -> None:
    port = _resolve_port(provision_config)
    provision_config["port"] = port
    ports = list(infra_config.get("ports") or [])
    if port not in ports:
        ports.append(port)
    infra_config["ports"] = ports


def provision(context: str, infra_config: dict, provision_config: dict) -> dict:
    if not context:
        raise ValueError("context is required")
    port = _resolve_port(provision_config)
    endpoint_id = _seed_endpoint_id(provision_config)
    endpoint_details = traefik.resolve_endpoint_details(endpoint_id)

    k8s.install_headlamp(context, port, base_url=endpoint_details["path_prefix"])
    token = k8s.create_headlamp_service_account_token(context)
    route = traefik.register_http_endpoint(route_name=endpoint_id, target_port=port)

    return {
        "endpoint_id": route["endpoint_id"],
        "route_name": route["route_name"],
        "route_config_file": route["config_file"],
        "url": route["url"],
        "hostname": route["domain_name"],
        "path_prefix": route["path_prefix"],
        "port": port,
        "token": token,
        "service_account": k8s.HEADLAMP_ADMIN_SERVICE_ACCOUNT,
        "service_account_namespace": k8s.HEADLAMP_SERVICE_NAMESPACE,
    }


def deprovision(context: str, infra_config: dict, provision_config: dict, provision_state: dict) -> None:
    endpoint_id = (provision_state or {}).get("endpoint_id")
    if not endpoint_id:
        endpoint_id = _seed_endpoint_id(provision_config)
    try:
        traefik.delete_http_endpoint(endpoint_id)
    except Exception as exc:
        print(f"warning: failed to delete Headlamp Traefik route '{endpoint_id}': {exc}")


def get_status(context: str, provision_config: dict, provision_state: dict) -> dict:
    if not context:
        return {"ready": False, "error": "context not set"}
    try:
        k8s._load_kube_config(context)
    except ConfigException as exc:
        return {"ready": False, "error": str(exc)}

    apps_api = client.AppsV1Api()
    try:
        deployment = apps_api.read_namespaced_deployment_status(
            name=k8s.HEADLAMP_DEPLOYMENT_NAME,
            namespace=k8s.HEADLAMP_SERVICE_NAMESPACE,
        )
    except client.ApiException as exc:
        if exc.status == 404:
            return {"ready": False, "error": "deployment not found"}
        return {"ready": False, "error": "api error"}
    except Exception:
        return {"ready": False, "error": "cluster unreachable"}

    spec_replicas = getattr(deployment.spec, "replicas", 0) or 0
    ready_replicas = getattr(deployment.status, "ready_replicas", 0) or 0
    return {
        "ready": ready_replicas > 0 and ready_replicas >= spec_replicas,
        "ready_replicas": ready_replicas,
        "replicas": spec_replicas,
        "url": (provision_state or {}).get("url"),
    }


def reconcile(
    infra_id: int,
    project_id: int,
    infra_name: str,
    context: str,
    infra_config: dict,
    provision_config: dict,
    provision_state: dict,
) -> dict | None:
    provision_config.setdefault("_seed", {"project_id": project_id, "infra_name": infra_name})
    port = _resolve_port(provision_config)
    endpoint_id = (provision_state or {}).get("endpoint_id") or _seed_endpoint_id(provision_config)

    route = traefik.register_http_endpoint(route_name=endpoint_id, target_port=port)

    new_state = dict(provision_state or {})
    new_state.update({
        "endpoint_id": route["endpoint_id"],
        "route_name": route["route_name"],
        "route_config_file": route["config_file"],
        "url": route["url"],
        "hostname": route["domain_name"],
        "path_prefix": route["path_prefix"],
        "port": port,
    })

    if context:
        try:
            k8s.configure_headlamp_base_url(context=context, base_url=route["path_prefix"])
        except Exception as exc:
            print(f"warning: failed to set Headlamp base URL for infra_id={infra_id}: {exc}")
        try:
            new_state["token"] = k8s.create_headlamp_service_account_token(context)
            new_state["service_account"] = k8s.HEADLAMP_ADMIN_SERVICE_ACCOUNT
            new_state["service_account_namespace"] = k8s.HEADLAMP_SERVICE_NAMESPACE
        except Exception as exc:
            print(f"warning: failed to refresh Headlamp token for infra_id={infra_id}: {exc}")

    if new_state == (provision_state or {}):
        return None
    return new_state
