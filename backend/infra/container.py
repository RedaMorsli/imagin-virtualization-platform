import socket
from typing import Any, Dict


def _coerce_port_int(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError("port must be an integer") from None
    if port < 1 or port > 65535:
        raise ValueError("port must be between 1 and 65535")
    return port


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def check_port_available(port: int) -> bool | int:
    """
    Return True if the port is available; otherwise return the next available port
    by incrementing.
    """
    port_int = _coerce_port_int(port)
    if _is_port_available(port_int):
        return True

    candidate = port_int + 1
    while candidate <= 65535:
        if _is_port_available(candidate):
            return candidate
        candidate += 1

    raise RuntimeError("no available port found")


def get_container_status(container_name: str) -> dict:
    """
    Return container status information. Possible statuses include:
    - running
    - exited
    - created
    - paused
    - restarting
    - removing
    - dead
    - not_found
    """
    if not container_name:
        raise ValueError("container_name is required")

    try:
        import docker
        from docker.errors import APIError, NotFound
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK is not installed; add 'docker' to requirements.txt") from exc

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        container.reload()
        return {"status": container.status, "id": container.id, "name": container.name}
    except NotFound:
        return {"status": "not_found"}
    except APIError as exc:
        detail = getattr(exc, "explanation", None) or str(exc)
        raise RuntimeError(f"docker API error: {detail}") from exc
    finally:
        client.close()


def remove_container(container_name: str, force: bool = True) -> bool:
    if not container_name:
        raise ValueError("container_name is required")

    try:
        import docker
        from docker.errors import APIError, NotFound
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK is not installed; add 'docker' to requirements.txt") from exc

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        container.remove(force=force)
        return True
    except NotFound:
        return False
    except APIError as exc:
        detail = getattr(exc, "explanation", None) or str(exc)
        raise RuntimeError(f"docker API error: {detail}") from exc
    finally:
        client.close()


def _coerce_port_value(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def _normalize_ports(ports: Any) -> dict | None:
    if ports is None:
        return None

    if isinstance(ports, dict):
        return ports

    if isinstance(ports, (list, tuple)):
        bindings: dict = {}
        for entry in ports:
            if not isinstance(entry, str):
                raise ValueError("ports entries must be strings like '8080:80'")

            parts = entry.split(":")
            if len(parts) == 2:
                host_port, container_port = parts
                host_ip = None
            elif len(parts) == 3:
                host_ip, host_port, container_port = parts
            else:
                raise ValueError(
                    "ports entries must be 'HOST:CONTAINER' or 'HOST_IP:HOST:CONTAINER'"
                )

            if not host_port or not container_port:
                raise ValueError("ports entries must include host and container ports")

            container_key = _coerce_port_value(container_port)
            host_binding = _coerce_port_value(host_port)
            if host_ip:
                host_binding = (host_ip, host_binding)

            bindings[container_key] = host_binding

        return bindings

    raise ValueError("ports must be a dict or list of strings")


def _normalize_volumes(volumes: Any) -> dict | list | None:
    if volumes is None:
        return None

    if isinstance(volumes, dict):
        normalized: dict = {}
        for host_path, spec in volumes.items():
            if isinstance(spec, str):
                normalized[host_path] = {"bind": spec, "mode": "rw"}
            elif isinstance(spec, dict):
                bind = spec.get("bind")
                if not bind:
                    raise ValueError("volume bindings must include a 'bind' path")
                mode = spec.get("mode", "rw")
                normalized[host_path] = {"bind": bind, "mode": mode}
            else:
                raise ValueError("volume bindings must be strings or dicts")
        return normalized

    if isinstance(volumes, (list, tuple)):
        binds: dict = {}
        container_paths: list[str] = []
        has_bind = False
        has_container_only = False

        for entry in volumes:
            if not isinstance(entry, str):
                raise ValueError("volumes entries must be strings")

            parts = entry.split(":")
            if len(parts) == 1:
                has_container_only = True
                container_paths.append(entry)
                continue
            if len(parts) not in (2, 3):
                raise ValueError("volume entries must be 'HOST:CONTAINER[:MODE]'")

            has_bind = True
            host_path, container_path = parts[0], parts[1]
            mode = parts[2] if len(parts) == 3 else "rw"
            binds[host_path] = {"bind": container_path, "mode": mode}

        if has_bind and has_container_only:
            raise ValueError("volumes cannot mix container-only paths and host binds")

        return binds if has_bind else container_paths

    raise ValueError("volumes must be a dict or list of strings")


def create_docker_container(config: Dict[str, Any]) -> dict:
    """
    Create a Docker container using the Python Docker SDK.

    Expected config keys:
      - image (str, required)
      - name (str, optional)
      - command/cmd (str|list, optional)
      - environment/env (dict|list, optional)
      - ports (dict|list, optional) e.g. {80: 8080} or ["8080:80"]
      - volumes (dict|list, optional) e.g. {"/host": {"bind": "/ct", "mode": "rw"}}
      - detach (bool, optional, default True)
      - remove/auto_remove (bool, optional)
      - network (str, optional)
      - restart_policy (dict|str, optional)
      - working_dir (str, optional)
      - labels (dict, optional)
      - tty (bool, optional)
      - stdin_open (bool, optional)
      - entrypoint (str|list, optional)
      - user (str|int, optional)
      - privileged (bool, optional)
      - extra_hosts (dict, optional)
    """
    if not isinstance(config, dict):
        raise ValueError("config must be a dictionary")

    image = config.get("image")
    if not image or not isinstance(image, str):
        raise ValueError("config must include 'image' as a string")

    name = config.get("name")
    command = config.get("command") or config.get("cmd")
    environment = config.get("environment") or config.get("env")
    ports = _normalize_ports(config.get("ports"))
    volumes = _normalize_volumes(config.get("volumes"))
    detach = bool(config.get("detach", True))
    auto_remove = bool(config.get("remove", config.get("auto_remove", False)))
    network = config.get("network")
    restart_policy = config.get("restart_policy")
    if isinstance(restart_policy, str):
        restart_policy = {"Name": restart_policy}

    try:
        import docker
        from docker.errors import APIError, ImageNotFound
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK is not installed; add 'docker' to requirements.txt") from exc

    client = docker.from_env()
    try:
        run_kwargs: dict = {
            "detach": detach,
            "tty": bool(config.get("tty", False)),
            "stdin_open": bool(config.get("stdin_open", False)),
            "privileged": bool(config.get("privileged", False)),
            "auto_remove": auto_remove,
        }

        if name:
            run_kwargs["name"] = name
        if command is not None:
            run_kwargs["command"] = command
        if environment is not None:
            run_kwargs["environment"] = environment
        if ports is not None:
            run_kwargs["ports"] = ports
        if volumes is not None:
            run_kwargs["volumes"] = volumes
        if network:
            run_kwargs["network"] = network
        if restart_policy:
            run_kwargs["restart_policy"] = restart_policy
        if config.get("working_dir"):
            run_kwargs["working_dir"] = config.get("working_dir")
        if config.get("labels"):
            run_kwargs["labels"] = config.get("labels")
        if config.get("entrypoint") is not None:
            run_kwargs["entrypoint"] = config.get("entrypoint")
        if config.get("user") is not None:
            run_kwargs["user"] = config.get("user")
        if config.get("extra_hosts"):
            run_kwargs["extra_hosts"] = config.get("extra_hosts")

        result = client.containers.run(image, **run_kwargs)
    except ImageNotFound as exc:
        raise RuntimeError(f"docker image not found: {image}") from exc
    except APIError as exc:
        detail = getattr(exc, "explanation", None) or str(exc)
        raise RuntimeError(f"docker API error: {detail}") from exc
    finally:
        client.close()

    if detach:
        return {"id": result.id, "name": result.name}

    output = result
    if isinstance(output, (bytes, bytearray)):
        output = output.decode(errors="replace")
    return {"output": output}
