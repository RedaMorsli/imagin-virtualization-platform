
from fastapi import APIRouter, HTTPException, status, Header, Response
from pydantic import BaseModel
import db
import api.auth as auth
import json
import re
from api.project import user_has_project_access
from infra.container import (
    create_docker_container,
    check_port_available,
    get_container_status,
    remove_container,
)

router = APIRouter(
    prefix="/storage",
    tags=["storage"],
)


# ============ SCHEMAS ============

class CreateStorageRequest(BaseModel):
    project_id: int
    infra_config: dict | None = None


class FetchStorageRequest(BaseModel):
    project_id: int


class FetchStorageResponse(BaseModel):
    storages: list[dict]


class StorageStatusRequest(BaseModel):
    project_id: int


class StorageStatusResponse(BaseModel):
    status: str


# ============ ENDPOINTS ============


@router.post("/create")
async def create_storage_endpoint(request: CreateStorageRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _create_storage(user['user_id'], request.project_id, request.infra_config or {})
        return Response(status_code=status.HTTP_200_OK)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/fetch", response_model=FetchStorageResponse)
async def fetch_storage_endpoint(request: FetchStorageRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _fetch_storages(user['user_id'], request.project_id)
        return FetchStorageResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/status", response_model=StorageStatusResponse)
async def storage_status_endpoint(request: StorageStatusRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _get_storage_status(user['user_id'], request.project_id)
        return StorageStatusResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    
    
# ============ LOGIC ============


_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]+")


def _slugify(value: str) -> str:
    name = _NAME_SAFE_RE.sub("-", value.strip().lower())
    name = name.strip("-.")
    return name or "project"


def _resolve_port(port_value: int) -> int:
    check = check_port_available(port_value)
    if check is True:
        return int(port_value)
    return int(check)


def _get_project_name(project_id: int) -> str:
    rows = db.fetch_all(
        """
        SELECT project_name
        FROM Projects
        WHERE project_id = ?
        """,
        params=[project_id],
    )
    if not rows:
        raise ValueError("Project not found")
    return rows[0][0]


def _ensure_storage_infra_column() -> None:
    columns = db.fetch_all("PRAGMA table_info('Projects');")
    if not any(col[1] == "storage_infra_id" for col in columns):
        db.execute("ALTER TABLE Projects ADD COLUMN storage_infra_id INTEGER")


def _create_storage(user_id: int, project_id: int, storage_config: dict):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    _ensure_storage_infra_column()
    current_status = _get_storage_status(user_id, project_id)
    if current_status.get("status") == "active":
        return

    project_name = _get_project_name(project_id)
    container_name = f"minio-{_slugify(project_name)}-{project_id}"

    existing = db.fetch_all(
        "SELECT infra_name FROM Infra WHERE infra_name = ?",
        params=[container_name],
    )
    if existing:
        raise ValueError("Infra already exists")

    requested_api_port = storage_config.get("api_port", 9000)
    requested_console_port = storage_config.get("console_port", 9001)

    api_port = _resolve_port(requested_api_port)
    console_port = _resolve_port(requested_console_port)
    if console_port == api_port:
        console_port = _resolve_port(console_port + 1)

    create_docker_container(
        {
            "image": "quay.io/minio/minio:latest",
            "name": container_name,
            "command": ["server", "/data", "--console-address", ":9001"],
            "environment": {
                "MINIO_ROOT_USER": "minioadmin",
                "MINIO_ROOT_PASSWORD": "minioadmin",
            },
            "ports": {9000: api_port, 9001: console_port},
            "detach": True,
        }
    )

    infra_config = {"api_port": api_port, "console_port": console_port}

    db.execute(
        "INSERT INTO Infra (project_id, infra_name, infra_type, infra_config) VALUES (?, ?, ?, ?)",
        params=[project_id, container_name, "storage", json.dumps(infra_config)],
    )

    infra_id = db.get_seq_last_val('seq_infra_id')
    db.execute(
        "UPDATE Projects SET storage_infra_id = ? WHERE project_id = ?",
        params=[infra_id, project_id],
    )


def _fetch_storages(user_id: int, project_id: int):
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    rows = db.fetch_all(
        """
        SELECT infra_id, infra_name, infra_type, infra_config
        FROM Infra
        WHERE project_id = ? AND infra_type = ?
        """,
        params=[project_id, "storage"],
    )

    storages = []
    for infra_id, infra_name, infra_type, infra_config in rows:
        storages.append(
            {
                "infra_id": infra_id,
                "infra_name": infra_name,
                "infra_type": infra_type,
                "infra_config": json.loads(infra_config),
            }
        )

    return {"storages": storages}


def _get_storage_status(user_id: int, project_id: int) -> dict:
    has_access = user_has_project_access(user_id, project_id)
    if not has_access:
        raise ValueError("User does not have access to this project")

    _ensure_storage_infra_column()

    rows = db.fetch_all(
        """
        SELECT storage_infra_id
        FROM Projects
        WHERE project_id = ?
        """,
        params=[project_id],
    )
    if not rows:
        raise ValueError("Project not found")

    storage_infra_id = rows[0][0]
    if not storage_infra_id:
        return {"status": "disabled"}

    infra_rows = db.fetch_all(
        """
        SELECT infra_name, infra_config
        FROM Infra
        WHERE infra_id = ? AND project_id = ? AND infra_type = ?
        """,
        params=[storage_infra_id, project_id, "storage"],
    )
    if not infra_rows:
        return {"status": "disabled"}

    container_name, infra_config_raw = infra_rows[0]
    infra_config = json.loads(infra_config_raw)

    status_info = get_container_status(container_name)
    if status_info.get("status") == "running":
        return {"status": "active"}

    remove_container(container_name, force=True)
    create_docker_container(
        {
            "image": "quay.io/minio/minio:latest",
            "name": container_name,
            "command": ["server", "/data", "--console-address", ":9001"],
            "environment": {
                "MINIO_ROOT_USER": "minioadmin",
                "MINIO_ROOT_PASSWORD": "minioadmin",
            },
            "ports": {9000: infra_config.get("api_port", 9000), 9001: infra_config.get("console_port", 9001)},
            "detach": True,
        }
    )

    return {"status": "active"}
