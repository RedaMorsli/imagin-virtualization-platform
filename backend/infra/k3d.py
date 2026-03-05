import json
import subprocess
from typing import Any, Dict


def _run_k3d_command(cmd: list[str], action: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{action} failed: {error_output}")
    return result


def create_k3d_cluster(config: Dict[str, Any], registry: str | None = None) -> str:
    cluster_name = config.get("name")
    if not cluster_name:
        raise ValueError("config must include 'name'")

    if "node_count" not in config:
        raise ValueError("config must include 'node_count'")

    try:
        node_count = int(config["node_count"])
    except (TypeError, ValueError):
        raise ValueError("'node_count' must be an integer") from None

    if node_count < 1:
        raise ValueError("'node_count' must be at least 1")

    agent_count = max(node_count - 1, 0)
    raw_ports = config.get("ports", [])
    if raw_ports is None:
        raw_ports = []
    if not isinstance(raw_ports, (list, tuple)):
        raise ValueError("'ports' must be an array of port numbers")

    ports: list[int] = []
    for raw_port in raw_ports:
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            raise ValueError("'ports' entries must be integers") from None

        if port < 1 or port > 65535:
            raise ValueError("'ports' entries must be between 1 and 65535")
        ports.append(port)

    cmd = ["k3d", "cluster", "create", cluster_name, "--servers", "1"]
    if registry:
        cmd.extend(["--registry-use", registry])
    if agent_count:
        cmd.extend(["--agents", str(agent_count)])
    for port in ports:
        cmd.extend(["-p", f"{port}:{port}@loadbalancer"])

    result = _run_k3d_command(cmd, "k3d cluster creation")

    print(cmd)

    kubeconfig_cmd = ["k3d", "kubeconfig", "merge", cluster_name]
    _run_k3d_command(kubeconfig_cmd, "kubeconfig merge")
    
    config['context'] = 'k3d-' + config.get("name")

    return result.stdout.strip()


def create_k3d_registry(config: Dict[str, Any]) -> str:
    """
    Create a local container registry managed by k3d.

    Expected config keys:
      - name (str): registry name (required)
      - port (int|str, optional): host port to expose (default: 5000)
      - host (str, optional): host interface (default: 0.0.0.0)
      - proxy_remote (str, optional): remote registry to proxy (passed to k3d)
    """
    name = config.get("name")
    if not name:
        raise ValueError("config must include 'name'")

    port = str(config.get("port", 5000))
    host = config.get("host", "0.0.0.0")

    port_flag = f"{host}:{port}"

    cmd = ["k3d", "registry", "create", name, "--port", port_flag]

    proxy_remote = config.get("proxy_remote")
    if proxy_remote:
        cmd.extend(["--proxy-remote-registry", proxy_remote])

    result = _run_k3d_command(cmd, "k3d registry creation")

    return result.stdout.strip()


def delete_k3d_cluster(cluster_name: str) -> str:
    if not cluster_name:
        raise ValueError("cluster_name is required")

    cmd = ["k3d", "cluster", "delete", cluster_name]
    result = _run_k3d_command(cmd, "k3d cluster deletion")
    return result.stdout.strip()


def get_registry_status(name: str) -> dict:
    """Return status information for a k3d-managed registry."""
    if not name:
        raise ValueError("registry name is required")

    result = subprocess.run(
        ["k3d", "registry", "list", "-o", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip()
        return {"status": "unknown", "error": error_output}

    try:
        registries = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("failed to parse k3d registry list output") from exc

    target_names = {name, f"k3d-{name}"}
    match = next(
        (
            reg
            for reg in registries
            if (reg.get("name") or reg.get("Name")) in target_names
        ),
        None,
    )

    if not match:
        return {"status": "not found"}

    state = match.get("state") or match.get("State") or {}
    status = state.get("status") or state.get("Status")

    if not status:
        running_flag = state.get("running") or state.get("Running")
        if running_flag is True:
            status = "running"
        elif running_flag is False:
            status = "stopped"
        else:
            status = "unknown"

    host = match.get("host") or match.get("Host")
    port = match.get("port") or match.get("Port")

    if not host or not port:
        options = match.get("options") or match.get("Options") or {}
        host = host or options.get("host") or options.get("Host")
        port = port or options.get("port") or options.get("Port")

    return {"status": status, "host": host, "port": port}
