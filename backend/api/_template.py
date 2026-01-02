
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel
import db
import api.auth as auth

router = APIRouter(
    prefix="/prefix",
    tags=["prefix"],
)


# ============ SCHEMAS ============

class NewRequest(BaseModel):
    request_var: str


class NewResponse(BaseModel):
    response_var: int


# ============ ENDPOINTS ============


@router.post("/routePost", response_model=NewResponse)
async def new_endpoint(request: NewRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _post_function(user['uid'], request.request_var)
        return NewResponse(**result)
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


def _post_function(user_id: int, var: str, ):
    existing = db.fetch_all(
        "SELECT param FROM Table WHERE name = ?",
        params=[var]
    )
    if existing:
        raise ValueError("Thing already exists")
    
    db.execute(
        "INSERT INTO Table (name) VALUES (?)",
        params=[var]
    )
    
    id = db.get_seq_last_val('seq')

    
    return {
        "project_id": id
        }


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
