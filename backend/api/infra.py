
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
import infra.k8s as k8s

router = APIRouter(
    prefix="/infra",
    tags=["infra"],
)


# ============ SCHEMAS ============

class CreateInfraRequest(BaseModel):
    project_id: int
    infra_type: str
    infra_config: dict


class FetchInfraRequest(BaseModel):
    project_id: int



class FetchInfraResponse(BaseModel):
    infras: list[dict]


# ============ ENDPOINTS ============


@router.post("/create")
async def create_infra_endpoint(request: CreateInfraRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _create_infra(user['user_id'], request.project_id, request.infra_type, request.infra_config)
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/fetch", response_model=FetchInfraResponse)
async def fetch_infras_endpoint(request: FetchInfraRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _fetch_infras(user['user_id'], request.project_id)
        return FetchInfraResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    
# ============ LOGIC ============


def _create_infra(user_id: int, project_id: int, infra_type: str, infra_config: dict):
    has_access = _user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    existing = db.fetch_all(
        "SELECT infra_name FROM Infra WHERE infra_name = ?",
        params=[infra_config.get("name")],
    )
    if existing:
        raise ValueError("Infra already exists")
    
    
    if infra_type == "cluster":
        from infra.k3d import create_k3d_cluster
        cluster_output = create_k3d_cluster(infra_config)

    db.execute(
        "INSERT INTO Infra (project_id, infra_name, infra_type, infra_config) VALUES (?, ?, ?, ?)",
        params=[project_id, infra_config.get("name"), infra_type, json.dumps(infra_config)]
    )
    

def _fetch_infras(user_id: int, project_id: int):
    has_access = _user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")
    
    rows = db.fetch_all(
        """
        SELECT infra_id, infra_type, infra_config
        FROM Infra i
        WHERE i.project_id = ?
        """,
        [project_id]
    )
    infras = [{
        "infra_id": id, 
        "infra_type": type, 
        "infra_config": json.loads(config), 
        "status": k8s.get_cluster_status(json.loads(config).get("context"))
        } for id, type, config in rows]
    # for infra in infras:
    #     infra['status'] = k8s.get_cluster_status(infra['infra_config']['context'])
    return {"infras": infras}


def _user_has_project_access(user_id: int, project_id: int) -> bool:
    access = db.fetch_all(
        """
        SELECT 1
        FROM ProjectUsers
        WHERE project_id = ? AND user_id = ?
        """,
        params=[project_id, user_id]
    )
    return bool(access)
