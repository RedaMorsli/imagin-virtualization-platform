import io
import os
import urllib.request
import urllib.error


def _get_endpoint() -> str:
    return os.environ.get("MINIO_ENDPOINT", "minio:9000")


def _get_client():
    try:
        from minio import Minio
    except ModuleNotFoundError as exc:
        raise RuntimeError("minio SDK is not installed; add 'minio' to requirements.txt") from exc

    endpoint = _get_endpoint()
    access_key = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)


def health_check() -> bool:
    """
    Check if the MinIO instance is ready to accept requests.

    Hits the MinIO readiness probe at /minio/health/ready.
    Returns True if healthy, raises RuntimeError otherwise.
    """
    endpoint = _get_endpoint()
    url = f"http://{endpoint}/minio/health/ready"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status == 200:
                return True
            raise RuntimeError(f"MinIO health check returned unexpected status {resp.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"MinIO health check failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MinIO is unreachable at {endpoint}: {exc.reason}") from exc


def ensure_bucket(bucket_name: str) -> None:
    """Create the bucket if it does not already exist."""
    try:
        from minio.error import S3Error
    except ModuleNotFoundError as exc:
        raise RuntimeError("minio SDK is not installed; add 'minio' to requirements.txt") from exc

    client = _get_client()
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except S3Error as exc:
        raise RuntimeError(f"Failed to ensure bucket '{bucket_name}': {exc}") from exc


def upload_object(
    bucket_name: str,
    object_name: str,
    data: io.BytesIO,
    length: int,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload an object to the given bucket."""
    try:
        from minio.error import S3Error
    except ModuleNotFoundError as exc:
        raise RuntimeError("minio SDK is not installed; add 'minio' to requirements.txt") from exc

    client = _get_client()
    try:
        client.put_object(bucket_name, object_name, data, length, content_type=content_type)
    except S3Error as exc:
        raise RuntimeError(f"Failed to upload '{object_name}' to bucket '{bucket_name}': {exc}") from exc


def delete_object(bucket_name: str, object_name: str) -> None:
    """Delete an object from the given bucket."""
    try:
        from minio.error import S3Error
    except ModuleNotFoundError as exc:
        raise RuntimeError("minio SDK is not installed; add 'minio' to requirements.txt") from exc

    client = _get_client()
    try:
        client.remove_object(bucket_name, object_name)
    except S3Error as exc:
        raise RuntimeError(f"Failed to delete '{object_name}' from bucket '{bucket_name}': {exc}") from exc


def list_bucket_objects(bucket_name: str) -> list[dict]:
    """List all objects in the given bucket. Returns [] if the bucket does not exist."""
    try:
        from minio.error import S3Error
    except ModuleNotFoundError as exc:
        raise RuntimeError("minio SDK is not installed; add 'minio' to requirements.txt") from exc

    client = _get_client()
    try:
        if not client.bucket_exists(bucket_name):
            return []
        return [
            {"name": obj.object_name, "size": obj.size or 0}
            for obj in client.list_objects(bucket_name, recursive=True)
        ]
    except S3Error as exc:
        raise RuntimeError(f"Failed to list objects in bucket '{bucket_name}': {exc}") from exc
