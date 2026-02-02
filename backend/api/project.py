
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel
import db
import api.auth as auth
import time

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


# ============ SCHEMAS ============

class CreateProjectRequest(BaseModel):
    project_name: str


class CreateProjectResponse(BaseModel):
    project_id: int


class FetchProjectsResponse(BaseModel):
    projects: list

# ============ ENDPOINTS ============


@router.post("/create", response_model=CreateProjectResponse)
async def create_project_endpoint(request: CreateProjectRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _create_project(request.project_name, user['user_id'])
        return CreateProjectResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/fetch", response_model=FetchProjectsResponse)
async def create_project_endpoint(authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _fetch_projects(user['user_id'])
        return FetchProjectsResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    
    
# ============ LOGIC ============


def user_has_project_access(user_id: int, project_id: int) -> bool:
    access = db.fetch_all(
        """
        SELECT 1
        FROM ProjectUsers
        WHERE project_id = ? AND user_id = ?
        """,
        params=[project_id, user_id]
    )
    return bool(access)


def _create_project(project_name: str, user_id: int):
    existing = db.fetch_all(
        "SELECT project_id FROM Projects WHERE project_name = ?",
        params=[project_name]
    )
    if existing:
        raise ValueError("Project already exists")
    
    db.execute(
        "INSERT INTO Projects (project_name) VALUES (?)",
        params=[project_name]
    )
    
    project_id = db.get_seq_last_val('seq_project_id')

    db.execute(
        "INSERT INTO ProjectUsers (project_id, user_id, project_role_id) VALUES (?, ?, ?)",
        params=[project_id, user_id, 1]
    )
    
    return {
        "project_id": project_id
        }


def _fetch_projects(user_id: int):
    rows = db.fetch_all(
        """
        SELECT p.project_id, p.project_name
        FROM ProjectUsers pu
        JOIN Projects p ON pu.project_id = p.project_id
        WHERE pu.user_id = ?
        """,
        params=[user_id]
    )
    projects = [{"project_id": pid, "project_name": pname} for pid, pname in rows]
    return {"projects": projects}
