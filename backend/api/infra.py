
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
import infra.k8s as k8s
import infra.traefik as traefik
from api.project import user_has_project_access

router = APIRouter(
    prefix="/infra",
    tags=["infra"],
)


# ============ SCHEMAS ============

class CreateInfraRequest(BaseModel):
    project_id: int
    infra_type: str
    infra_config: dict
    provision: dict | None = None


class FetchInfraRequest(BaseModel):
    project_id: int



class FetchInfraResponse(BaseModel):
    infras: list[dict]


class KubeconfigRequest(BaseModel):
    project_id: int
    infra_id: int


class KubeconfigResponse(BaseModel):
    kubeconfig: str


# ============ ENDPOINTS ============


@router.post("/create")
async def create_infra_endpoint(request: CreateInfraRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _create_infra(user['user_id'], request.project_id, request.infra_type, request.infra_config, request.provision)
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/fetch", response_model=FetchInfraResponse)
async def fetch_infras_endpoint(project_id: int, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _fetch_infras(user['user_id'], project_id)
        return FetchInfraResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/kubeconfig", response_model=KubeconfigResponse)
async def fetch_kubeconfig_endpoint(request: KubeconfigRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _get_kubeconfig(user['user_id'], request.project_id, request.infra_id)
        return KubeconfigResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    
# ============ LOGIC ============


def _uses_headlamp_web_ui(infra_config: dict) -> bool:
    if infra_config.get("web_ui") is True:
        return True
    for key in (
        "web_ui_url",
        "web_ui_route_name",
        "web_ui_endpoint_id",
        "web_ui_port",
    ):
        if key in infra_config:
            return True
    return False


def _resolve_web_ui_port(infra_config: dict) -> int:
    raw_port = infra_config.get("web_ui_port", k8s.HEADLAMP_NODE_PORT)
    try:
        parsed_port = int(raw_port)
    except (TypeError, ValueError):
        raise ValueError("'web_ui_port' must be an integer") from None
    if parsed_port < 1 or parsed_port > 65535:
        raise ValueError("'web_ui_port' must be between 1 and 65535")
    return parsed_port


def _legacy_route_name_from_hostname(hostname: str) -> str | None:
    normalized = str(hostname or "").strip().strip(".").lower()
    if not normalized:
        return None
    labels = [label for label in normalized.split(".") if label]
    if len(labels) < 3:
        # New path-based URLs store the root domain only; that is not a route id.
        return None
    return labels[0]


def _stable_headlamp_seed(project_id: int, infra_name: str | None) -> str:
    normalized_name = str(infra_name or "").strip()
    if not normalized_name:
        normalized_name = "cluster"
    return f"headlamp-p{project_id}-{normalized_name}"


def _resolve_web_ui_endpoint_id(project_id: int, infra_name: str | None, infra_config: dict) -> str:
    candidate_ids = [
        infra_config.get("web_ui_endpoint_id"),
        infra_config.get("web_ui_route_name"),
        _legacy_route_name_from_hostname(infra_config.get("web_ui_hostname", "")),
    ]
    for candidate_id in candidate_ids:
        if candidate_id is None:
            continue
        candidate_text = str(candidate_id).strip()
        if not candidate_text:
            continue
        return traefik.build_endpoint_id(candidate_text)
    return traefik.build_endpoint_id(_stable_headlamp_seed(project_id, infra_name))


def _apply_web_ui_route_metadata(infra_config: dict, route_details: dict) -> bool:
    updated = False
    updates = {
        "web_ui": True,
        "web_ui_endpoint_id": route_details["endpoint_id"],
        "web_ui_route_name": route_details["route_name"],
        "web_ui_route_config_file": route_details["config_file"],
        "web_ui_url": route_details["url"],
        "web_ui_hostname": route_details["domain_name"],
        "web_ui_path_prefix": route_details["path_prefix"],
    }
    for key, value in updates.items():
        if infra_config.get(key) != value:
            infra_config[key] = value
            updated = True
    return updated


def _reconcile_cluster_web_ui_route(
    infra_id: int,
    project_id: int,
    infra_name: str | None,
    infra_config: dict,
    fail_on_headlamp_error: bool = False,
) -> bool:
    if not _uses_headlamp_web_ui(infra_config):
        return False

    endpoint_id = _resolve_web_ui_endpoint_id(project_id, infra_name, infra_config)
    web_ui_port = _resolve_web_ui_port(infra_config)
    route_details = traefik.register_http_endpoint(route_name=endpoint_id, target_port=web_ui_port)
    base_url = f"{route_details['path_prefix']}/"

    context = str(infra_config.get("context", "")).strip()
    if context:
        try:
            k8s.configure_headlamp_base_url(context=context, base_url=base_url)
        except Exception as exc:
            if fail_on_headlamp_error:
                raise
            print(
                f"warning: failed to set Headlamp base URL for infra_id={infra_id}, "
                f"context='{context}': {exc}"
            )
    elif fail_on_headlamp_error:
        raise ValueError("Cluster context not found while configuring Headlamp base URL")

    updated = _apply_web_ui_route_metadata(infra_config, route_details)
    if infra_config.get("web_ui_port") != web_ui_port:
        infra_config["web_ui_port"] = web_ui_port
        updated = True
    return updated


def reconcile_cluster_web_ui_endpoints(project_id: int | None = None) -> dict:
    where_clause = "infra_type = ?"
    params: list = ["cluster"]
    if project_id is not None:
        where_clause += " AND project_id = ?"
        params.append(project_id)

    rows = db.fetch_all(
        f"""
        SELECT infra_id, project_id, infra_name, infra_config
        FROM Infra
        WHERE {where_clause}
        """,
        params=params,
    )

    reconciled_count = 0
    updated_count = 0
    error_count = 0

    for infra_id, row_project_id, infra_name, raw_config in rows:
        try:
            infra_config = json.loads(raw_config)
        except (TypeError, json.JSONDecodeError):
            print(f"warning: skipped infra_id={infra_id} due to invalid JSON config")
            error_count += 1
            continue

        if not _uses_headlamp_web_ui(infra_config):
            continue

        reconciled_count += 1
        try:
            was_updated = _reconcile_cluster_web_ui_route(
                infra_id=infra_id,
                project_id=row_project_id,
                infra_name=infra_name,
                infra_config=infra_config,
                fail_on_headlamp_error=False,
            )
        except Exception as exc:
            print(f"warning: failed to reconcile infra_id={infra_id}: {exc}")
            error_count += 1
            continue

        if was_updated:
            db.execute(
                "UPDATE Infra SET infra_config = ? WHERE infra_id = ?",
                params=[json.dumps(infra_config), infra_id],
            )
            updated_count += 1

    return {
        "reconciled": reconciled_count,
        "updated": updated_count,
        "errors": error_count,
    }


def _create_infra(user_id: int, project_id: int, infra_type: str, infra_config: dict, provision: dict = None):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    existing = db.fetch_all(
        "SELECT infra_name FROM Infra WHERE infra_name = ? AND project_id = ?",
        params=[infra_config.get("name"), project_id],
    )
    if existing:
        raise ValueError("Infra already exists")
    
    
    if infra_type == "cluster":
        from infra.k3d import create_k3d_cluster
        registry_use = None
        if "registry_infra_id" in infra_config and infra_config.get("registry_infra_id") is not None:
            try:
                registry_infra_id = int(infra_config.get("registry_infra_id"))
            except (TypeError, ValueError):
                raise ValueError("'registry_infra_id' must be an integer") from None

            registry_rows = db.fetch_all(
                """
                SELECT infra_config
                FROM Infra
                WHERE infra_id = ? AND infra_type = ? AND project_id = ?
                """,
                params=[registry_infra_id, "registry", project_id],
            )
            if not registry_rows:
                raise ValueError("Registry infra not found for provided id")

            try:
                registry_config = json.loads(registry_rows[0][0])
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Stored registry config is invalid") from exc

            registry_name = registry_config.get("name")
            if not registry_name:
                raise ValueError("Registry infra config missing 'name'")
            registry_port = registry_config.get("port", 5000)
            registry_use = f"k3d-{registry_name}:{registry_port}"

        if infra_config.get("web_ui") is True:
            web_ui_port = _resolve_web_ui_port(infra_config)
            endpoint_id = _resolve_web_ui_endpoint_id(project_id, infra_config.get("name"), infra_config)
            endpoint_details = traefik.resolve_endpoint_details(endpoint_id)
            infra_config["web_ui_port"] = web_ui_port
            infra_config['ports'] = [web_ui_port]

        cluster_output = create_k3d_cluster(infra_config, registry=registry_use)

        if infra_config.get("web_ui") is True:
            context = infra_config.get("context")
            if not context:
                raise ValueError("Cluster context not found after cluster creation")
            k8s.install_headlamp(context, web_ui_port, base_url=f"{endpoint_details['path_prefix']}/")
            infra_config["web_ui_token"] = k8s.create_headlamp_service_account_token(context)
            infra_config["web_ui_service_account"] = k8s.HEADLAMP_ADMIN_SERVICE_ACCOUNT
            infra_config["web_ui_service_account_namespace"] = k8s.HEADLAMP_SERVICE_NAMESPACE
            route_details = traefik.register_http_endpoint(
                route_name=endpoint_id,
                target_port=web_ui_port,
            )
            _apply_web_ui_route_metadata(infra_config, route_details)

        if provision is not None:
            if provision['name'] == "flower":
                from infra.flower import provision_flower_on_cluster
                provision_flower_on_cluster(infra_config['context'], provision)

    db.execute(
        "INSERT INTO Infra (project_id, infra_name, infra_type, infra_config) VALUES (?, ?, ?, ?)",
        params=[project_id, infra_config.get("name"), infra_type, json.dumps(infra_config)]
    )
    

def _fetch_infras(user_id: int, project_id: int):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")
    
    try:
        reconcile_cluster_web_ui_endpoints(project_id=project_id)
    except Exception as exc:
        print(f"warning: project endpoint reconciliation failed for project_id={project_id}: {exc}")

    rows = db.fetch_all(
        """
        SELECT infra_id, infra_type, infra_config
        FROM Infra i
        WHERE i.project_id = ? AND infra_type = ?
        """,
        [project_id, "cluster"]
    )

    infras = []
    for infra_id, infra_type, raw_config in rows:
        config_dict = json.loads(raw_config)
        context = config_dict.get("context")
        status_payload = (
            k8s.get_cluster_status(context)
            if infra_type == "cluster" and context
            else {}
        )
        infras.append(
            {
                "infra_id": infra_id,
                "infra_type": infra_type,
                "infra_config": config_dict,
                "status": status_payload,
            }
        )

    return {"infras": infras}


def _get_kubeconfig(user_id: int, project_id: int, infra_id: int):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    rows = db.fetch_all(
        """
        SELECT infra_config
        FROM Infra
        WHERE infra_id = ? AND project_id = ?
        """,
        params=[infra_id, project_id],
    )

    if not rows:
        raise ValueError("Infra not found")

    infra_config = json.loads(rows[0][0])
    context = infra_config.get("context")
    if not context:
        raise ValueError("Infra kube context not found")
    try:
        kubeconfig_content = k8s.get_raw_kubeconfig(context, rewrite_host="localhost")
    except Exception as exc:
        raise ValueError(f"Failed to load kubeconfig: {exc}") from exc

    return {"kubeconfig": kubeconfig_content}
