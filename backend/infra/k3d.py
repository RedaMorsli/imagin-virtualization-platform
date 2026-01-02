import subprocess
from typing import Any, Dict


def create_k3d_cluster(config: Dict[str, Any]) -> str:
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

    cmd = ["k3d", "cluster", "create", cluster_name, "--servers", "1"]
    if agent_count:
        cmd.extend(["--agents", str(agent_count)])

    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"k3d cluster creation failed: {error_output}")

    return result.stdout.strip()
