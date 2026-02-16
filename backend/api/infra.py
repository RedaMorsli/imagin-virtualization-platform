
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
import infra.k8s as k8s
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

        cluster_output = create_k3d_cluster(infra_config, registry=registry_use)
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
    
    rows = db.fetch_all(
        """
        SELECT infra_id, infra_type, infra_config
        FROM Infra i
        WHERE i.project_id = ? AND infra_type = ?
        """,
        [project_id, "cluster"]
    )
    infras = [{
        "infra_id": id, 
        "infra_type": type, 
        "infra_config": json.loads(config), 
        "status": (
            k8s.get_cluster_status(json.loads(config).get("context"))
            if type == "cluster" and json.loads(config).get("context")
            else {}
        ),
        } for id, type, config in rows]
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


