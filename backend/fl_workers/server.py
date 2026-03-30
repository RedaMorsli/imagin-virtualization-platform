"""
FL Server — runs inside a Docker container, one per FL run.

Environment variables:
    RUN_ID              integer, mandatory
    FL_NUM_ROUNDS       number of federated rounds (default 3)
    FL_NUM_CLIENTS      number of clients that must connect (default 2)
    PLATFORM_URL        base URL of the platform backend (default http://backend:8000)
    METRIC_LOGGING      "local" or "wandb" (default "local")
    WANDB_API_KEY       W&B API key (required when METRIC_LOGGING=wandb)
    WANDB_ENTITY        W&B entity / team name (optional)
    WANDB_PROJECT       W&B project name
    WANDB_RUN_NAME      W&B run name
"""

import os
import requests
import flwr as fl
from flwr.server.strategy import FedAvg

RUN_ID         = int(os.environ["RUN_ID"])
NUM_ROUNDS     = int(os.environ.get("FL_NUM_ROUNDS", "3"))
NUM_CLIENTS    = int(os.environ.get("FL_NUM_CLIENTS", "2"))
PLATFORM_URL   = os.environ.get("PLATFORM_URL", "http://backend:8000")
METRIC_LOGGING = os.environ.get("METRIC_LOGGING", "local")
WANDB_API_KEY  = os.environ.get("WANDB_API_KEY", "")
WANDB_ENTITY   = os.environ.get("WANDB_ENTITY", "") or None
WANDB_PROJECT  = os.environ.get("WANDB_PROJECT", "fl-platform")
WANDB_RUN_NAME = os.environ.get("WANDB_RUN_NAME", f"run-{RUN_ID}")

print(f"[server] run_id={RUN_ID} rounds={NUM_ROUNDS} clients={NUM_CLIENTS}")
print(f"[server] metric_logging={METRIC_LOGGING}")

_wandb_run = None

if METRIC_LOGGING == "wandb":
    if not WANDB_API_KEY:
        print("[server] warn: METRIC_LOGGING=wandb but WANDB_API_KEY is empty — skipping wandb")
    else:
        print(f"[server] initialising wandb entity='{WANDB_ENTITY}' project='{WANDB_PROJECT}' run='{WANDB_RUN_NAME}'")
        try:
            import wandb
            wandb.login(key=WANDB_API_KEY)
            _wandb_run = wandb.init(
                entity=WANDB_ENTITY,
                project=WANDB_PROJECT,
                name=WANDB_RUN_NAME,
                config={
                    "run_id":      RUN_ID,
                    "num_rounds":  NUM_ROUNDS,
                    "num_clients": NUM_CLIENTS,
                    "role":        "server",
                },
            )
            print(f"[server] wandb run initialised: {_wandb_run.url}")
        except Exception as exc:
            print(f"[server] warn: wandb init failed: {exc}")
            _wandb_run = None
else:
    print("[server] metric_logging=local, wandb disabled")


def _post(path: str, payload: dict) -> None:
    try:
        requests.post(f"{PLATFORM_URL}{path}", json=payload, timeout=5)
    except Exception as exc:
        print(f"[server] warn: failed to POST {path}: {exc}")


class ReportingFedAvg(FedAvg):
    """FedAvg that POSTs per-round metrics to the platform and optionally logs to W&B."""

    def aggregate_evaluate(self, server_round, results, failures):
        aggregated = super().aggregate_evaluate(server_round, results, failures)
        if aggregated is None:
            return aggregated
        loss, metrics = aggregated
        round_metrics = {
            "loss": float(loss),
            **{k: float(v) for k, v in metrics.items()},
        }

        # Always post to local DB
        _post("/experiments/runs/metrics", {
            "run_id":  RUN_ID,
            "round":   server_round,
            "metrics": round_metrics,
        })

        # Also log to W&B when enabled
        if _wandb_run is not None:
            try:
                _wandb_run.log(
                    {f"server/{k}": v for k, v in round_metrics.items()},
                    step=server_round,
                )
                print(f"[server] wandb logged round {server_round}: {round_metrics}")
            except Exception as exc:
                print(f"[server] warn: wandb.log failed: {exc}")

        return aggregated


strategy = ReportingFedAvg(
    min_fit_clients=NUM_CLIENTS,
    min_evaluate_clients=NUM_CLIENTS,
    min_available_clients=NUM_CLIENTS,
    on_fit_config_fn=lambda rnd: {"server_round": str(rnd), "local_epochs": "1"},
)

fl.server.start_server(
    server_address="0.0.0.0:8080",
    config=fl.server.ServerConfig(num_rounds=NUM_ROUNDS),
    strategy=strategy,
)

_post("/experiments/runs/complete", {"run_id": RUN_ID, "status": "completed"})

if _wandb_run is not None:
    try:
        _wandb_run.finish()
        print("[server] wandb run finished")
    except Exception:
        pass
