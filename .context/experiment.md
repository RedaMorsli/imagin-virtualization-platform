# Federated Learning Experiment System — Implementation Summary

---

## Concept & Architecture

Experiments are a **generic platform concept** with a `type` field. `fl_flower` is the first type. The system has two levels:

- **Experiment** — a named template storing configuration (clients, rounds, resource limits, metric logging)
- **Run** — an execution of an experiment, tracked with status, timestamps, and per-round metrics

FL runs are executed using **Flower (flwr==1.14.0)** in classic client-server mode. Each run spins up real Docker containers via the Docker SDK — one server container and N client containers — rather than using Flower's simulation engine. This was a deliberate choice because Flower's SuperLink/SuperNode (process-based simulation) is a paid feature.

---

## Database Schema

Added to `backend/db_init.sql`:

```sql
CREATE TABLE ExperimentRuns (
    run_id INTEGER PRIMARY KEY DEFAULT nextval('seq_run_id'),
    experiment_id INTEGER NOT NULL REFERENCES Experiments(experiment_id),
    run_config TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'provisioning',  -- provisioning | running | completed | failed
    started_at TIMESTAMP DEFAULT (now()),
    finished_at TIMESTAMP
);

CREATE TABLE RunMetrics (
    metric_id INTEGER PRIMARY KEY DEFAULT nextval('seq_run_metric_id'),
    run_id INTEGER NOT NULL REFERENCES ExperimentRuns(run_id),
    round INTEGER NOT NULL,
    metric_name VARCHAR(64) NOT NULL,
    metric_value FLOAT NOT NULL,
    recorded_at TIMESTAMP DEFAULT (now())
);
```

---

## Backend Files

### `backend/api/experiment.py`
Full REST API for experiments and runs.

Key endpoints:
- `POST /experiments/create` — stores experiment with JSON config in DB
- `GET /experiments/fetch?project_id=X` — returns experiments with embedded runs and `final_metrics`
- `POST /experiments/delete` — tears down active runs, removes DB records
- `POST /experiments/runs/launch` — creates a `provisioning` run record, fires `_background_launch` in a daemon thread, returns `run_id` immediately
- `GET /experiments/runs/fetch?experiment_id=X`
- `POST /experiments/runs/metrics` — **no auth**, called by FL server container to POST per-round metrics
- `POST /experiments/runs/complete` — **no auth**, called by FL server when all rounds finish; triggers async `teardown_run`

Key internal functions:
- `_background_launch(run_id, config, project_name)` — calls `ensure_worker_image()` then `launch_run()`, updates status to `running` or `failed`
- `_get_project_name_for_experiment(experiment_id)` — JOIN `Projects` + `Experiments` to resolve `project_name` for W&B

### `backend/infra/fl_docker.py`
Manages Docker lifecycle for FL runs.

- `ensure_worker_image()` — builds `imagin-fl-worker:latest` from `backend/fl_workers/` if not present; called at platform startup and before each launch
- `launch_run(run_id, config, platform_url, project_name)` — creates isolated bridge network `fl-net-{run_id}`, starts `fl-server-{run_id}`, connects server to `platform_net` (so it can POST callbacks to backend), waits 3s, starts N `fl-client-{run_id}-{i}` containers
- `teardown_run(run_id)` — force-removes all containers and network for a run
- `get_run_container_status(run_id)` — returns live Docker status per container

**Critical networking detail**: The FL server container is connected to **two networks** — the isolated `fl-net-{run_id}` (to communicate with clients via gRPC) and the shared `platform_net` (to POST metrics/completion callbacks to `http://backend:8000`). Clients only need `fl-net-{run_id}`.

Env vars passed to all containers via `shared_env`:
```python
{
    "METRIC_LOGGING": "local" | "wandb",
    "WANDB_API_KEY":  "...",
    "WANDB_ENTITY":   "...",
    "WANDB_PROJECT":  project_name,
    "WANDB_RUN_NAME": experiment_name,
}
```

---

## FL Worker Containers

Built from `backend/fl_workers/` into image `imagin-fl-worker:latest`.

### `backend/fl_workers/Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py client.py ./
```

### `backend/fl_workers/requirements.txt`
```
flwr==1.14.0
torch
torchvision
requests
numpy
wandb
```

### `backend/fl_workers/server.py`
- Reads env vars: `RUN_ID`, `FL_NUM_ROUNDS`, `FL_NUM_CLIENTS`, `PLATFORM_URL`, `METRIC_LOGGING`, `WANDB_*`
- If `METRIC_LOGGING=wandb`: calls `wandb.login(key=WANDB_API_KEY)` then `wandb.init(...)`, stores run object as `_wandb_run`
- `ReportingFedAvg(FedAvg)` overrides two methods:
  - `aggregate_fit` — computes weighted average `train_loss` from client fit metrics, logs as `global/train_loss`
  - `aggregate_evaluate` — aggregates eval loss/accuracy, POSTs to `/experiments/runs/metrics` (always), logs as `global/loss`, `global/accuracy` to W&B
- Strategy uses `on_fit_config_fn` and `on_evaluate_config_fn` — both pass `{"server_round": str(rnd)}` so clients always know the current round
- After `fl.server.start_server` returns: POSTs to `/experiments/runs/complete`, calls `_wandb_run.finish()`

### `backend/fl_workers/client.py`
- Trains a `MNISTModel` (simple CNN) on an IID shard of MNIST
- Data partitioning: `CLIENT_ID * shard_size` to `(CLIENT_ID+1) * shard_size`
- If `METRIC_LOGGING=wandb`: `wandb.login()` + `wandb.init()` with `group=WANDB_RUN_NAME` so all clients for a run are grouped in W&B dashboard
- `fit()`: trains for `local_epochs`, logs `client/train_loss` at `step=server_round`, **returns** `{"train_loss": train_loss}` in metrics dict so server can aggregate
- `evaluate()`: reads `server_round` from config (not from instance state), logs `client/eval_loss` and `client/eval_accuracy` at correct step

---

## W&B Metrics Structure

| Metric key | Source | Logged by |
|---|---|---|
| `global/train_loss` | Weighted avg of client fit metrics | Server `aggregate_fit` |
| `global/loss` | Weighted avg of client eval loss | Server `aggregate_evaluate` |
| `global/accuracy` | Weighted avg of client eval accuracy | Server `aggregate_evaluate` |
| `client/train_loss` | Per-client local training | Each client `fit()` |
| `client/eval_loss` | Per-client evaluation | Each client `evaluate()` |
| `client/eval_accuracy` | Per-client evaluation | Each client `evaluate()` |

All metrics use `step=server_round` so they align correctly on the W&B timeline. Client runs are grouped under the experiment name via `group=WANDB_RUN_NAME`.

---

## Docker Compose Changes

`docker-compose.yaml` additions:
- All services joined to named network `platform_net` (name: `platform_net`)
- Backend env vars: `PLATFORM_URL: http://backend:8000`, `PLATFORM_NETWORK: platform_net`

`backend/main.py` startup: calls `fl_docker.ensure_worker_image()` to pre-build the worker image when the platform starts. The image is **not** rebuilt automatically if it already exists — manual `docker rmi imagin-fl-worker:latest` is required after worker code changes.

---

## Frontend Files

### `frontend/pages/project_detail/experiments/new_experiment_dialog.gd`
Dialog for creating a new FL experiment. Sends `experiment_config`:
```json
{
  "name": "...",
  "num_clients": 2,
  "num_rounds": 3,
  "cpu_limit": "500m",
  "memory_limit_mb": 512,
  "metric_logging": "local" | "wandb",
  "wandb_api_key": "..."
}
```
The `WandbKeyContainer` row is hidden unless "Wandb" is selected in `MetricOptionButton`.

### `frontend/pages/project_detail/experiments/experiment_card.gd`
`class_name ExperimentCard extends PanelContainer`. Built programmatically in `_ready()`. Uses a `FoldableContainer` (collapsed by default). On first expand, lazily fetches runs via `API.fetch_runs_url`. Shows each run as a row with status (theme-colored), date, final accuracy/loss.

### `frontend/pages/project_detail/experiments/experiment_management_view.gd`
`extends VBoxContainer`. Fetches all experiments for the project on ready, instantiates one `ExperimentCard` per experiment.

---

## `start.sh`
Convenience script at project root:
```bash
docker build -t imagin-fl-worker:latest ./backend/fl_workers
docker compose -f docker-compose.yaml up --build -d
```
Builds the FL worker image first (since compose doesn't manage it), then builds and starts all platform services detached.
