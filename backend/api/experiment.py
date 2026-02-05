
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
from api.project import user_has_project_access

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
)


# ============ SCHEMAS ============

class CreateExperimentRequest(BaseModel):
    project_id: int
    experiment_type: str
    experiment_config: dict


class FetchExperimentRequest(BaseModel):
    project_id: int


class FetchExperimentResponse(BaseModel):
    experiments: list[dict]


# ============ ENDPOINTS ============


@router.post("/create")
async def create_experiment_endpoint(request: CreateExperimentRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _create_experiment(user['user_id'], request.project_id, request.experiment_type, request.experiment_config)
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/fetch", response_model=FetchExperimentResponse)
async def fetch_experiment_endpoint(request: FetchExperimentRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _fetch_experiments(user['user_id'], request.project_id)
        return FetchExperimentResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


# ============ LOGIC ============


def _create_experiment(user_id: int, project_id: int, experiment_type: str, experiment_config: dict):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    existing = db.fetch_all(
        "SELECT experiment_name FROM Experiments WHERE experiment_name = ? AND project_id = ?",
        params=[experiment_config.get("name"), project_id],
    )
    if existing:
        raise ValueError("Experiment already exists")
    
    
    if experiment_type == "fl_flower":
        print("Creating FL Flower experiment with config:", experiment_config)

    db.execute(
        "INSERT INTO Experiments (project_id, experiment_name, experiment_type, experiment_config) VALUES (?, ?, ?, ?)",
        params=[project_id, experiment_config.get("name"), experiment_type, json.dumps(experiment_config)]
    )
    

def _fetch_experiments(user_id: int, project_id: int):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")
    
    rows = db.fetch_all(
        """
        SELECT experiment_id, experiment_type, experiment_config
        FROM Experiments i
        WHERE i.project_id = ? AND experiment_type = ?
        """,
        [project_id, "cluster"]
    )
    infras = [{
        "experiment_id": id, 
        "experiment_type": type, 
        "experiment_config": json.loads(config)
        } for id, type, config in rows]
    return {"experiments": infras}



