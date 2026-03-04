import hashlib
import os
import re
import tempfile
from typing import Dict

import yaml

TRAEFIK_DYNAMIC_DIR_ENV = "TRAEFIK_DYNAMIC_DIR"
DOMAIN_NAME_ENV = "DOMAIN_NAME"
ENDPOINT_TARGET_HOST_ENV = "ENDPOINT_TARGET_HOST"
ENDPOINT_PATH_BASE_ENV = "ENDPOINT_PATH_BASE"

DEFAULT_TRAEFIK_DYNAMIC_DIR = "/app/traefik-dynamic"
DEFAULT_ENDPOINT_TARGET_HOST = "host.docker.internal"
DEFAULT_ENDPOINT_PATH_BASE = "/endpoints"
ENDPOINT_FILE_PREFIX = "endpoint-"
MAX_DNS_LABEL_LENGTH = 63
HASH_SUFFIX_LENGTH = 8


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower().strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError("route name cannot be empty after sanitization")
    return slug


def _bounded_dns_label(value: str) -> str:
    label = _slugify(value)
    if len(label) <= MAX_DNS_LABEL_LENGTH:
        return label
    return label[:MAX_DNS_LABEL_LENGTH].rstrip("-")


def _router_name(route_name: str) -> str:
    base = _slugify(route_name)

    # If caller already passes a stable hashed route name, reuse it.
    if re.fullmatch(r"[a-z0-9-]+-[0-9a-f]{8}", base):
        return _bounded_dns_label(base)

    suffix = hashlib.sha1(route_name.encode("utf-8")).hexdigest()[:HASH_SUFFIX_LENGTH]
    max_base_len = MAX_DNS_LABEL_LENGTH - HASH_SUFFIX_LENGTH - 1
    bounded_base = base[:max_base_len].rstrip("-")
    if not bounded_base:
        bounded_base = "endpoint"
    return f"{bounded_base}-{suffix}"


def _resolve_dynamic_dir() -> str:
    dynamic_dir = os.environ.get(TRAEFIK_DYNAMIC_DIR_ENV, DEFAULT_TRAEFIK_DYNAMIC_DIR).strip()
    if not dynamic_dir:
        raise RuntimeError("TRAEFIK_DYNAMIC_DIR is empty")
    return dynamic_dir


def _resolve_domain_name() -> str:
    domain_name = os.environ.get(DOMAIN_NAME_ENV, "").strip().strip(".").lower()
    if not domain_name:
        raise RuntimeError("DOMAIN_NAME is required")
    return domain_name


def _resolve_endpoint_path_base() -> str:
    endpoint_path_base = os.environ.get(
        ENDPOINT_PATH_BASE_ENV, DEFAULT_ENDPOINT_PATH_BASE
    ).strip()
    if not endpoint_path_base:
        raise RuntimeError("ENDPOINT_PATH_BASE is empty")
    if not endpoint_path_base.startswith("/"):
        endpoint_path_base = f"/{endpoint_path_base}"
    endpoint_path_base = re.sub(r"/{2,}", "/", endpoint_path_base).rstrip("/")
    if endpoint_path_base in ("", "/"):
        raise RuntimeError("ENDPOINT_PATH_BASE must not resolve to '/'")
    return endpoint_path_base


def _write_yaml_atomic(path: str, payload: Dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".yaml",
            prefix=".tmp-",
            dir=directory,
            delete=False,
        ) as tmp_file:
            yaml.safe_dump(payload, tmp_file, sort_keys=False)
            temp_path = tmp_file.name
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def build_endpoint_id(seed: str) -> str:
    if not seed:
        raise ValueError("seed is required")
    return _router_name(seed)


def resolve_endpoint_details(endpoint_id: str) -> Dict[str, str]:
    normalized_endpoint_id = build_endpoint_id(endpoint_id)
    domain_name = _resolve_domain_name()
    endpoint_path_prefix = f"{_resolve_endpoint_path_base()}/{normalized_endpoint_id}"
    return {
        "endpoint_id": normalized_endpoint_id,
        "domain_name": domain_name,
        "path_prefix": endpoint_path_prefix,
        "url": f"https://{domain_name}{endpoint_path_prefix}/",
    }


def register_http_endpoint(route_name: str, target_port: int | str) -> Dict[str, str]:
    if not route_name:
        raise ValueError("route_name is required")
    try:
        parsed_port = int(target_port)
    except (TypeError, ValueError):
        raise ValueError("target_port must be an integer") from None
    if parsed_port < 1 or parsed_port > 65535:
        raise ValueError("target_port must be between 1 and 65535")

    endpoint_target_host = os.environ.get(
        ENDPOINT_TARGET_HOST_ENV, DEFAULT_ENDPOINT_TARGET_HOST
    ).strip()
    if not endpoint_target_host:
        raise RuntimeError("ENDPOINT_TARGET_HOST is empty")

    endpoint_details = resolve_endpoint_details(route_name)
    endpoint_id = endpoint_details["endpoint_id"]
    domain_name = endpoint_details["domain_name"]
    endpoint_path_prefix = endpoint_details["path_prefix"]
    endpoint_url = endpoint_details["url"]
    target_url = f"http://{endpoint_target_host}:{parsed_port}"
    file_name = f"{ENDPOINT_FILE_PREFIX}{endpoint_id}.yaml"
    output_path = os.path.join(_resolve_dynamic_dir(), file_name)

    config = {
        "http": {
            "routers": {
                endpoint_id: {
                    "rule": (
                        f"Host(`{domain_name}`) && "
                        f"(Path(`{endpoint_path_prefix}`) || "
                        f"PathPrefix(`{endpoint_path_prefix}/`))"
                    ),
                    "entryPoints": ["websecure"],
                    "service": endpoint_id,
                    "tls": {},
                }
            },
            "services": {
                endpoint_id: {
                    "loadBalancer": {
                        "servers": [
                            {"url": target_url},
                        ]
                    }
                }
            },
        }
    }

    _write_yaml_atomic(output_path, config)

    return {
        "route_name": endpoint_id,
        "endpoint_id": endpoint_id,
        "hostname": domain_name,
        "domain_name": domain_name,
        "path_prefix": endpoint_path_prefix,
        "url": endpoint_url,
        "target_url": target_url,
        "config_file": file_name,
    }


def delete_http_endpoint(route_name: str) -> bool:
    if not route_name:
        raise ValueError("route_name is required")
    endpoint_id = build_endpoint_id(route_name)
    path = os.path.join(_resolve_dynamic_dir(), f"{ENDPOINT_FILE_PREFIX}{endpoint_id}.yaml")
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
