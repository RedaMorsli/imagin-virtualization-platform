
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
from api.project import user_has_project_access

router = APIRouter(
    prefix="/registry",
    tags=["registry"],
)


# ============ SCHEMAS ============

class CreateRegistryRequest(BaseModel):
    project_id: int
    infra_config: dict

# ============ ENDPOINTS ============


@router.post("/create")
async def create_registry_endpoint(request: CreateRegistryRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _create_registry(user['user_id'], request.project_id, request.infra_config)
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    
    
# ============ LOGIC ============

def _create_registry(user_id: int, project_id: int, registry_config: dict):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    existing = db.fetch_all(
        "SELECT infra_name FROM Infra WHERE infra_name = ? AND project_id = ?",
        params=[registry_config.get("name"), project_id],
    )
    if existing:
        raise ValueError("Infra already exists")

    from infra.k3d import create_k3d_registry
    create_k3d_registry(registry_config)

    db.execute(
        "INSERT INTO Infra (project_id, infra_name, infra_type, infra_config) VALUES (?, ?, ?, ?)",
        params=[project_id, registry_config.get("name"), "registry", json.dumps(registry_config)]
    )
