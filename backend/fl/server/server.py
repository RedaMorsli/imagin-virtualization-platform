from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import flwr as fl

from config import ExperimentConfig, load_experiment_config
from dataset import DatasetBundle, load_dataset
from user_logic import (
    build_runtime_context,
    load_user_entrypoint,
    prepare_user_environment,
    resolve_user_server_components,
)


def _series_to_payload(series: list[tuple[int, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for server_round, value in series:
        item: dict[str, Any] = {"round": int(server_round)}
        if isinstance(value, (int, float)):
            item["value"] = float(value)
        else:
            item["value"] = str(value)
        payload.append(item)
    return payload


def _metrics_to_payload(metrics: dict[str, list[tuple[int, Any]]]) -> dict[str, list[dict[str, Any]]]:
    payload: dict[str, list[dict[str, Any]]] = {}
    for metric_name, series in metrics.items():
        payload[metric_name] = _series_to_payload(series)
    return payload


def _history_to_payload(history: fl.server.history.History) -> dict[str, Any]:
    return {
        "losses_distributed": _series_to_payload(getattr(history, "losses_distributed", [])),
        "losses_centralized": _series_to_payload(getattr(history, "losses_centralized", [])),
        "metrics_distributed": _metrics_to_payload(getattr(history, "metrics_distributed", {})),
        "metrics_distributed_fit": _metrics_to_payload(getattr(history, "metrics_distributed_fit", {})),
        "metrics_centralized": _metrics_to_payload(getattr(history, "metrics_centralized", {})),
    }


def _write_run_result(
    config: ExperimentConfig,
    run_index: int,
    dataset: DatasetBundle,
    history: fl.server.history.History,
) -> Path:
    output_dir = Path(config.results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_index": run_index + 1,
        "config": asdict(config),
        "dataset": {
            "train_samples": int(dataset.train_x.shape[0]),
            "test_samples": int(dataset.test_x.shape[0]),
            "num_features": int(dataset.train_x.shape[1]),
        },
        "history": _history_to_payload(history),
    }

    run_output_path = output_dir / f"{config.run_name}_run_{run_index + 1}.json"
    with run_output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    return run_output_path


def _run_single_experiment(config: ExperimentConfig, dataset: DatasetBundle, run_index: int, user_entrypoint) -> Path:
    runtime_context = build_runtime_context(config=config, dataset=dataset, run_index=run_index)
    components = user_entrypoint(runtime_context)
    resolved_components = resolve_user_server_components(components, default_num_rounds=config.num_rounds)

    print(
        f"[Run {run_index + 1}/{config.num_runs}] Waiting for clients at {config.server_address} "
        f"(min_available_clients={config.min_available_clients})"
    )
    history = fl.server.start_server(
        server_address=config.server_address,
        config=resolved_components.server_config,
        strategy=resolved_components.strategy,
    )

    output_path = _write_run_result(
        config=config,
        run_index=run_index,
        dataset=dataset,
        history=history,
    )
    print(f"[Run {run_index + 1}/{config.num_runs}] Saved metrics to {output_path}")
    return output_path


def main() -> None:
    config = load_experiment_config()
    dataset = load_dataset(config)
    user_code_dir = prepare_user_environment(config)
    user_entrypoint = load_user_entrypoint(config, user_code_dir)

    print(
        f"Loaded dataset with train={dataset.train_x.shape[0]} test={dataset.test_x.shape[0]} "
        f"features={dataset.train_x.shape[1]}"
    )
    print(
        "Experiment config: "
        f"rounds={config.num_rounds}, runs={config.num_runs}, "
        f"fraction_fit={config.fraction_fit}, fraction_evaluate={config.fraction_evaluate}"
    )

    for run_index in range(config.num_runs):
        _run_single_experiment(
            config=config,
            dataset=dataset,
            run_index=run_index,
            user_entrypoint=user_entrypoint,
        )

    print("All experiment runs completed")


if __name__ == "__main__":
    main()
