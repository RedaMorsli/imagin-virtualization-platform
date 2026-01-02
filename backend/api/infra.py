
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth

router = APIRouter(
    prefix="/infra",
    tags=["infra"],
)


# ============ SCHEMAS ============

class CreateInfraRequest(BaseModel):
    project_id: int
    infra_type: str
    infra_config: dict


class NewResponse(BaseModel):
    response_var: int


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


@router.get("/routeGet", response_model=NewResponse)
async def create_project_endpoint(authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _get_function(user['user_id'])
        return NewResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    
    
# ============ LOGIC ============


def _create_infra(user_id: int, project_id: int, infra_type: str, infra_config: dict):
    existing = db.fetch_all(
        "SELECT infra_name FROM Infra WHERE infra_name = ?",
        params=[infra_config.get("name")],
    )
    if existing:
        raise ValueError("Infra already exists")
    
    db.execute(
        "INSERT INTO Infra (project_id, infra_name, infra_type, infra_config) VALUES (?, ?, ?, ?)",
        params=[project_id, infra_config.get("name"), infra_type, infra_config]
    )

    if infra_type == "cluster":
        from infra.k3d import create_k3d_cluster
        cluster_output = create_k3d_cluster(infra_config)
    
    


def _get_function(user_id: int):
    rows = db.fetch_all(
        """
        SELECT id, name
        FROM Table t
        WHERE t.id = ?
        """,
        user_id
    )
    things = [{"id": id, "name": name} for id, name in rows]
    return {"things": things}
