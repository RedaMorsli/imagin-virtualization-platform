import io
from fastapi import APIRouter, HTTPException, status, Header, Response, UploadFile, File, Form
from pydantic import BaseModel
import api.auth as auth
from api.project import user_has_project_access
import infra.minio as minio

router = APIRouter(
    prefix="/storage",
    tags=["storage"],
)


# ============ SCHEMAS ============

class DeleteFileRequest(BaseModel):
    project_id: int
    object_name: str


class FileEntry(BaseModel):
    name: str
    size: int


class ListFilesResponse(BaseModel):
    files: list[FileEntry]


# ============ ENDPOINTS ============


@router.post("/upload")
async def upload_file_endpoint(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        await _upload_file(user["user_id"], project_id, file)
        return Response(status_code=status.HTTP_200_OK)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.delete("/file")
async def delete_file_endpoint(request: DeleteFileRequest, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        _delete_file(user["user_id"], request.project_id, request.object_name)
        return Response(status_code=status.HTTP_200_OK)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("/files", response_model=ListFilesResponse)
async def list_files_endpoint(project_id: int, authorization: str = Header(None)):
    user = auth.get_user_by_token(auth.get_token(authorization))
    try:
        result = _list_files(user["user_id"], project_id)
        return ListFilesResponse(**result)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


# ============ LOGIC ============


def _bucket_name(project_id: int) -> str:
    return f"project-{project_id}"


def _check_access(user_id: int, project_id: int) -> None:
    if not user_has_project_access(user_id, project_id):
        raise PermissionError("User does not have access to this project")


async def _upload_file(user_id: int, project_id: int, file: UploadFile) -> None:
    _check_access(user_id, project_id)
    minio.health_check()
    bucket = _bucket_name(project_id)
    minio.ensure_bucket(bucket)
    data = await file.read()
    minio.upload_object(
        bucket,
        file.filename,
        io.BytesIO(data),
        len(data),
        content_type=file.content_type or "application/octet-stream",
    )


def _delete_file(user_id: int, project_id: int, object_name: str) -> None:
    _check_access(user_id, project_id)
    minio.health_check()
    bucket = _bucket_name(project_id)
    minio.delete_object(bucket, object_name)


def _list_files(user_id: int, project_id: int) -> dict:
    _check_access(user_id, project_id)
    minio.health_check()
    bucket = _bucket_name(project_id)
    files = minio.list_bucket_objects(bucket)
    return {"files": files}
