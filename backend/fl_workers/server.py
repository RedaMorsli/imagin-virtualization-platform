"""
FL Server — runs inside a Docker container, one per FL run.

Environment variables:
    RUN_ID                      integer, mandatory
    FL_NUM_ROUNDS               number of federated rounds (default 3)
    FL_NUM_CLIENTS              total number of clients (default 2)
    PLATFORM_URL                base URL of the platform backend (default http://backend:8000)
    METRIC_LOGGING              "local" or "wandb" (default "local")
    CLIENT_SELECTION_ALGORITHM  client selection algorithm name (default "all")
    CLIENT_SELECTION_PARAMS     JSON string of algorithm parameters (default "{}")
    WANDB_API_KEY               W&B API key (required when METRIC_LOGGING=wandb)
    WANDB_ENTITY                W&B entity / team name (optional)
    WANDB_PROJECT               W&B project name
    WANDB_RUN_NAME              W&B run name
"""

import json
import os
import random
import time

import requests
import flwr as fl
from flwr.common import FitIns, EvaluateIns
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

CLIENT_SELECTION_ALGORITHM = os.environ.get("CLIENT_SELECTION_ALGORITHM", "all")
CLIENT_SELECTION_PARAMS    = json.loads(os.environ.get("CLIENT_SELECTION_PARAMS", "{}"))

print(f"[server] run_id={RUN_ID} rounds={NUM_ROUNDS} clients={NUM_CLIENTS}")
print(f"[server] metric_logging={METRIC_LOGGING}")
print(f"[server] client_selection: algorithm={CLIENT_SELECTION_ALGORITHM} params={CLIENT_SELECTION_PARAMS}")

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
                    "client_selection_algorithm": CLIENT_SELECTION_ALGORITHM,
                    "client_selection_params":    CLIENT_SELECTION_PARAMS,
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


def _wandb_log(metrics: dict, step: int) -> None:
    if _wandb_run is None:
        return
    try:
        _wandb_run.log(metrics, step=step)
    except Exception as exc:
        print(f"[server] warn: wandb.log failed: {exc}")


# ── Client Selection ─────────────────────────────────────────────────────────

def select_clients(server_round, total_clients, algorithm, params):
    """Return sorted list of selected client indices for this round."""
    if algorithm == "random":
        num_selected = max(1, min(int(params.get("num_selected", 3)), total_clients))
        return sorted(random.sample(range(total_clients), num_selected))
    # "all" or unknown — select every client
    return list(range(total_clients))


# Mapping from Flower cid to container CLIENT_ID (built during round 1)
_cid_to_client_id = {}


def _manage_clients(action, client_ids):
    """Call the platform backend to pause or unpause client containers."""
    if not client_ids:
        return
    try:
        requests.post(f"{PLATFORM_URL}/experiments/runs/manage-clients", json={
            "run_id": RUN_ID,
            "action": action,
            "client_ids": client_ids,
        }, timeout=10)
    except Exception as exc:
        print(f"[server] warn: failed to {action} clients {client_ids}: {exc}")


# ── Strategy ─────────────────────────────────────────────────────────────────

class ReportingFedAvg(FedAvg):
    """FedAvg with per-round client selection, metrics reporting, and container management."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_selected_ids = list(range(NUM_CLIENTS))
        self._current_selected_cids = set()   # Flower CIDs chosen this round
        self._mapping_built = False

    # ── configure / aggregate: fit ────────────────────────────────────────

    def configure_fit(self, server_round, parameters, client_manager):
        use_selection = CLIENT_SELECTION_ALGORITHM != "all" and server_round > 1

        # Unpause any clients paused from the previous round
        if use_selection:
            _manage_clients("unpause", list(range(NUM_CLIENTS)))
            time.sleep(1)

        config = {"server_round": str(server_round), "local_epochs": "1"}
        fit_ins = FitIns(parameters, config)

        all_clients = list(client_manager.all().values())

        if not use_selection:
            # Round 1 or algorithm=="all" — all clients participate
            self._current_selected_ids = list(range(NUM_CLIENTS))
            selected_clients = all_clients
        else:
            selected_ids = select_clients(
                server_round, NUM_CLIENTS,
                CLIENT_SELECTION_ALGORITHM, CLIENT_SELECTION_PARAMS,
            )
            self._current_selected_ids = selected_ids

            if len(selected_ids) >= NUM_CLIENTS:
                selected_clients = all_clients
            elif self._mapping_built:
                # Mapping available — select precise proxies + pause containers
                selected_cids = {
                    cid for cid, clt_id in _cid_to_client_id.items()
                    if clt_id in selected_ids
                }
                selected_clients = [c for c in all_clients if c.cid in selected_cids]

                unselected_ids = [i for i in range(NUM_CLIENTS) if i not in selected_ids]
                _manage_clients("pause", unselected_ids)
            else:
                # Mapping not ready — pick random proxies (no Docker pausing)
                print("[server] warn: cid mapping not ready, selecting random proxies without container pausing")
                num_to_pick = min(len(selected_ids), len(all_clients))
                selected_clients = random.sample(all_clients, num_to_pick)

        self._current_selected_cids = {c.cid for c in selected_clients}

        num_selected = len(selected_clients)
        print(f"[server] round {server_round} — selected {num_selected}/{NUM_CLIENTS} clients: {self._current_selected_ids}")

        _wandb_log({
            "selection/num_selected":  num_selected,
            "selection/total_clients": NUM_CLIENTS,
            "selection/ratio":         num_selected / NUM_CLIENTS if NUM_CLIENTS > 0 else 0,
        }, step=server_round)

        _post("/experiments/runs/metrics", {
            "run_id":  RUN_ID,
            "round":   server_round,
            "metrics": {"num_selected_clients": num_selected},
        })

        return [(client, fit_ins) for client in selected_clients]

    def aggregate_fit(self, server_round, results, failures):
        # Build cid → client_id mapping from client fit metrics
        for client_proxy, fit_res in results:
            client_id = fit_res.metrics.get("client_id")
            if client_id is not None:
                _cid_to_client_id[client_proxy.cid] = int(client_id)

        if len(_cid_to_client_id) >= NUM_CLIENTS and not self._mapping_built:
            self._mapping_built = True
            print(f"[server] cid→client_id mapping complete: {dict(_cid_to_client_id)}")

        aggregated = super().aggregate_fit(server_round, results, failures)

        # Compute weighted average of train_loss reported by clients
        total_examples = 0
        weighted_loss  = 0.0
        for client_proxy, fit_res in results:
            n = fit_res.num_examples
            loss = fit_res.metrics.get("train_loss")
            if loss is not None:
                weighted_loss  += float(loss) * n
                total_examples += n

        if total_examples > 0:
            avg_train_loss = weighted_loss / total_examples
            print(f"[server] round {server_round} — global train_loss={avg_train_loss:.4f}")
            _wandb_log({"global/train_loss": avg_train_loss}, step=server_round)

        return aggregated

    # ── configure / aggregate: evaluate ───────────────────────────────────

    def configure_evaluate(self, server_round, parameters, client_manager):
        config = {"server_round": str(server_round)}
        eval_ins = EvaluateIns(parameters, config)

        all_clients = list(client_manager.all().values())

        if CLIENT_SELECTION_ALGORITHM == "all" or server_round <= 1:
            return [(c, eval_ins) for c in all_clients]

        # Reuse the exact proxy set from configure_fit
        selected_clients = [c for c in all_clients if c.cid in self._current_selected_cids]
        return [(c, eval_ins) for c in selected_clients]

    def aggregate_evaluate(self, server_round, results, failures):
        aggregated = super().aggregate_evaluate(server_round, results, failures)
        if aggregated is None:
            return aggregated
        loss, metrics = aggregated
        round_metrics = {
            "loss": float(loss),
            **{k: float(v) for k, v in metrics.items()},
        }

        print(f"[server] round {server_round} — global eval: {round_metrics}")

        # Always post to local DB
        _post("/experiments/runs/metrics", {
            "run_id":  RUN_ID,
            "round":   server_round,
            "metrics": round_metrics,
        })

        # Log global eval metrics to W&B
        _wandb_log({f"global/{k}": v for k, v in round_metrics.items()}, step=server_round)

        return aggregated


strategy = ReportingFedAvg(
    min_fit_clients=NUM_CLIENTS,
    min_evaluate_clients=NUM_CLIENTS,
    min_available_clients=NUM_CLIENTS,
)

fl.server.start_server(
    server_address="0.0.0.0:8080",
    config=fl.server.ServerConfig(num_rounds=NUM_ROUNDS),
    strategy=strategy,
)

# Unpause all clients before exit (in case any are still paused)
if CLIENT_SELECTION_ALGORITHM != "all":
    _manage_clients("unpause", list(range(NUM_CLIENTS)))

_post("/experiments/runs/complete", {"run_id": RUN_ID, "status": "completed"})

if _wandb_run is not None:
    try:
        _wandb_run.finish()
        print("[server] wandb run finished")
    except Exception:
        pass
