"""
FL Docker — manages per-run Flower containers.

Each run gets:
  - An isolated Docker bridge network  (fl-net-{run_id})
  - One server container               (fl-server-{run_id})
  - N client containers                (fl-client-{run_id}-{i})

The server container is also connected to the platform network so it can
POST metrics/completion callbacks to the backend.
"""

import os
import time

WORKER_IMAGE    = "imagin-fl-worker:latest"
PLATFORM_NETWORK = os.environ.get("PLATFORM_NETWORK", "platform_net")
_WORKERS_DIR    = os.path.join(os.path.dirname(__file__), "..", "fl_workers")


# ── Image management ──────────────────────────────────────────────────────────

def ensure_worker_image() -> None:
    """Build the FL worker Docker image if it is not already present."""
    try:
        import docker
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK not installed") from exc

    dc = docker.from_env()
    try:
        try:
            dc.images.get(WORKER_IMAGE)
            print(f"[fl_docker] image {WORKER_IMAGE} already present")
            return
        except docker.errors.ImageNotFound:
            pass

        print(f"[fl_docker] building {WORKER_IMAGE} …")
        _, logs = dc.images.build(
            path=os.path.abspath(_WORKERS_DIR),
            tag=WORKER_IMAGE,
            rm=True,
        )
        for chunk in logs:
            if "stream" in chunk:
                print(chunk["stream"], end="")
        print(f"[fl_docker] {WORKER_IMAGE} built successfully")
    finally:
        dc.close()


# ── Name helpers ──────────────────────────────────────────────────────────────

def _net_name(run_id: int) -> str:
    return f"fl-net-{run_id}"

def _server_name(run_id: int) -> str:
    return f"fl-server-{run_id}"

def _client_name(run_id: int, idx: int) -> str:
    return f"fl-client-{run_id}-{idx}"


# ── Launch / teardown ─────────────────────────────────────────────────────────

def launch_run(run_id: int, config: dict, platform_url: str, project_name: str = "") -> None:
    """
    Create the FL network, start the server container, then start N clients.

    config keys (all optional, defaults shown):
        num_clients     (2)
        num_rounds      (3)
        cpu_limit       ("500m"  — millicores string)
        memory_limit_mb (512)
        metric_logging  ("local" or "wandb")
        wandb_api_key   ("")
    """
    try:
        import docker
        from docker.errors import APIError
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK not installed") from exc

    num_clients      = int(config.get("num_clients", 2))
    num_rounds       = int(config.get("num_rounds", 3))
    cpu_limit        = str(config.get("cpu_limit", "500m"))
    memory_limit_mb  = int(config.get("memory_limit_mb", 512))
    metric_logging   = str(config.get("metric_logging", "local"))
    wandb_api_key    = str(config.get("wandb_api_key", ""))
    wandb_entity     = str(config.get("wandb_entity", ""))
    experiment_name  = str(config.get("name", f"run-{run_id}"))
    wandb_project    = project_name or f"project-{run_id}"
    wandb_run_name   = experiment_name

    if cpu_limit.endswith("m"):
        cpu_cores = int(cpu_limit[:-1]) / 1000.0
    else:
        cpu_cores = float(cpu_limit)

    shared_env = {
        "METRIC_LOGGING": metric_logging,
        "WANDB_API_KEY":  wandb_api_key,
        "WANDB_ENTITY":   wandb_entity,
        "WANDB_PROJECT":  wandb_project,
        "WANDB_RUN_NAME": wandb_run_name,
    }

    dc = docker.from_env()
    try:
        dc.networks.create(_net_name(run_id), driver="bridge")

        server = dc.containers.run(
            WORKER_IMAGE,
            command="python /app/server.py",
            name=_server_name(run_id),
            environment={
                "RUN_ID":         str(run_id),
                "FL_NUM_ROUNDS":  str(num_rounds),
                "FL_NUM_CLIENTS": str(num_clients),
                "PLATFORM_URL":   platform_url,
                **shared_env,
            },
            network=_net_name(run_id),
            detach=True,
        )

        # Connect the server to the platform network so it can call the backend.
        try:
            platform_net = dc.networks.get(PLATFORM_NETWORK)
            platform_net.connect(server)
        except Exception as exc:
            print(f"[fl_docker] warn: could not connect server to {PLATFORM_NETWORK}: {exc}")

        # Short wait for the server's gRPC listener to be ready before clients connect.
        time.sleep(3)

        for i in range(num_clients):
            dc.containers.run(
                WORKER_IMAGE,
                command="python /app/client.py",
                name=_client_name(run_id, i),
                environment={
                    "CLIENT_ID":      str(i),
                    "FL_NUM_CLIENTS": str(num_clients),
                    "SERVER_HOST":    _server_name(run_id),
                    "SERVER_PORT":    "8080",
                    **shared_env,
                },
                network=_net_name(run_id),
                nano_cpus=int(cpu_cores * 1e9),
                mem_limit=f"{memory_limit_mb}m",
                detach=True,
            )

    except APIError as exc:
        detail = getattr(exc, "explanation", None) or str(exc)
        teardown_run(run_id)
        raise RuntimeError(f"Failed to launch FL run {run_id}: {detail}") from exc
    finally:
        dc.close()


def teardown_run(run_id: int) -> None:
    """Force-remove all containers and the network for a run."""
    try:
        import docker
        from docker.errors import NotFound, APIError
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK not installed") from exc

    dc = docker.from_env()
    try:
        _remove_container(dc, _server_name(run_id))
        for i in range(64):
            if not _remove_container(dc, _client_name(run_id, i)):
                break
        try:
            dc.networks.get(_net_name(run_id)).remove()
        except NotFound:
            pass
        except APIError as exc:
            print(f"[fl_docker] warn: could not remove network {_net_name(run_id)}: {exc}")
    finally:
        dc.close()


def _remove_container(dc, name: str) -> bool:
    try:
        import docker
        from docker.errors import NotFound
    except ModuleNotFoundError:
        return False
    try:
        dc.containers.get(name).remove(force=True)
        return True
    except NotFound:
        return False


# ── Status ────────────────────────────────────────────────────────────────────

def get_run_container_status(run_id: int) -> dict:
    """Return container statuses: {"server": str, "clients": [str, ...]}"""
    try:
        import docker
        from docker.errors import NotFound
    except ModuleNotFoundError as exc:
        raise RuntimeError("docker SDK not installed") from exc

    dc = docker.from_env()
    try:
        def _status(name: str) -> str:
            try:
                c = dc.containers.get(name)
                c.reload()
                return c.status
            except NotFound:
                return "not_found"

        clients = []
        for i in range(64):
            name = _client_name(run_id, i)
            try:
                c = dc.containers.get(name)
                c.reload()
                clients.append(c.status)
            except NotFound:
                break

        return {"server": _status(_server_name(run_id)), "clients": clients}
    finally:
        dc.close()
