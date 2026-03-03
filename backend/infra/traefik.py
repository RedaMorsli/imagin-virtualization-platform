import hashlib
import os
import re
import tempfile
from typing import Dict

import yaml

TRAEFIK_DYNAMIC_DIR_ENV = "TRAEFIK_DYNAMIC_DIR"
APPS_BASE_DOMAIN_ENV = "APPS_BASE_DOMAIN"
DOMAIN_NAME_ENV = "DOMAIN_NAME"
ENDPOINT_TARGET_HOST_ENV = "ENDPOINT_TARGET_HOST"

DEFAULT_TRAEFIK_DYNAMIC_DIR = "/app/traefik-dynamic"
DEFAULT_ENDPOINT_TARGET_HOST = "host.docker.internal"
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


def _resolve_apps_base_domain() -> str:
    explicit_domain = os.environ.get(APPS_BASE_DOMAIN_ENV, "").strip().strip(".").lower()
    if explicit_domain:
        return explicit_domain

    root_domain = os.environ.get(DOMAIN_NAME_ENV, "").strip().strip(".").lower()
    if not root_domain:
        raise RuntimeError(
            "Cannot resolve apps base domain. Set APPS_BASE_DOMAIN or DOMAIN_NAME."
        )
    return f"apps.{root_domain}"


def _resolve_dynamic_dir() -> str:
    dynamic_dir = os.environ.get(TRAEFIK_DYNAMIC_DIR_ENV, DEFAULT_TRAEFIK_DYNAMIC_DIR).strip()
    if not dynamic_dir:
        raise RuntimeError("TRAEFIK_DYNAMIC_DIR is empty")
    return dynamic_dir


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


def register_http_endpoint(route_name: str, target_port: int | str) -> Dict[str, str]:
    if not route_name:
        raise ValueError("route_name is required")
    try:
        parsed_port = int(target_port)
    except (TypeError, ValueError):
        raise ValueError("target_port must be an integer") from None
    if parsed_port < 1 or parsed_port > 65535:
        raise ValueError("target_port must be between 1 and 65535")

    apps_base_domain = _resolve_apps_base_domain()
    endpoint_target_host = os.environ.get(
        ENDPOINT_TARGET_HOST_ENV, DEFAULT_ENDPOINT_TARGET_HOST
    ).strip()
    if not endpoint_target_host:
        raise RuntimeError("ENDPOINT_TARGET_HOST is empty")

    router_name = _router_name(route_name)
    hostname = f"{router_name}.{apps_base_domain}"
    target_url = f"http://{endpoint_target_host}:{parsed_port}"
    file_name = f"{ENDPOINT_FILE_PREFIX}{router_name}.yaml"
    output_path = os.path.join(_resolve_dynamic_dir(), file_name)

    config = {
        "http": {
            "routers": {
                router_name: {
                    "rule": f"Host(`{hostname}`)",
                    "entryPoints": ["websecure"],
                    "service": router_name,
                    "tls": {},
                }
            },
            "services": {
                router_name: {
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
        "route_name": router_name,
        "hostname": hostname,
        "url": f"https://{hostname}",
        "target_url": target_url,
        "config_file": file_name,
    }


def delete_http_endpoint(route_name: str) -> bool:
    if not route_name:
        raise ValueError("route_name is required")
    router_name = _router_name(route_name)
    path = os.path.join(_resolve_dynamic_dir(), f"{ENDPOINT_FILE_PREFIX}{router_name}.yaml")
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
