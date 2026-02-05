from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentConfig:
    server_address: str
    num_runs: int
    num_rounds: int
    fraction_fit: float
    fraction_evaluate: float
    min_available_clients: int
    min_fit_clients: int
    min_evaluate_clients: int
    learning_rate: float
    local_epochs: int
    batch_size: int
    data_division: str
    dataset_path: str | None
    label_column: str
    test_split: float
    random_seed: int
    synthetic_samples: int
    synthetic_features: int
    results_dir: str
    run_name: str
    user_code_dir: str
    user_entrypoint: str
    user_requirements_path: str
    install_user_requirements: bool


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float") from exc


def _read_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    if not value:
        raise ValueError(f"{name} must be non-empty when set")
    return value


def _read_optional_str(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean (true/false)")


def _validate_config(config: ExperimentConfig) -> None:
    if config.num_runs < 1:
        raise ValueError("FL_NUM_RUNS must be >= 1")
    if config.num_rounds < 1:
        raise ValueError("FL_NUM_ROUNDS must be >= 1")
    if config.min_available_clients < 1:
        raise ValueError("FL_MIN_AVAILABLE_CLIENTS must be >= 1")
    if config.min_fit_clients < 1:
        raise ValueError("FL_MIN_FIT_CLIENTS must be >= 1")
    if config.min_evaluate_clients < 1:
        raise ValueError("FL_MIN_EVAL_CLIENTS must be >= 1")
    if config.min_fit_clients > config.min_available_clients:
        raise ValueError("FL_MIN_FIT_CLIENTS cannot be greater than FL_MIN_AVAILABLE_CLIENTS")
    if config.min_evaluate_clients > config.min_available_clients:
        raise ValueError("FL_MIN_EVAL_CLIENTS cannot be greater than FL_MIN_AVAILABLE_CLIENTS")
    if not 0.0 < config.fraction_fit <= 1.0:
        raise ValueError("FL_FRACTION_FIT must be in (0, 1]")
    if not 0.0 <= config.fraction_evaluate <= 1.0:
        raise ValueError("FL_FRACTION_EVALUATE must be in [0, 1]")
    if config.learning_rate <= 0:
        raise ValueError("FL_LEARNING_RATE must be > 0")
    if config.local_epochs < 1:
        raise ValueError("FL_LOCAL_EPOCHS must be >= 1")
    if config.batch_size < 1:
        raise ValueError("FL_BATCH_SIZE must be >= 1")
    if not 0.0 < config.test_split < 1.0:
        raise ValueError("FL_TEST_SPLIT must be in (0, 1)")
    if config.synthetic_samples < 4:
        raise ValueError("FL_SYNTHETIC_SAMPLES must be >= 4")
    if config.synthetic_features < 1:
        raise ValueError("FL_SYNTHETIC_FEATURES must be >= 1")
    if ":" not in config.user_entrypoint:
        raise ValueError("FL_USER_ENTRYPOINT must be in '<module_or_file>:<callable>' format")


def load_experiment_config() -> ExperimentConfig:
    config = ExperimentConfig(
        server_address=_read_str("FL_SERVER_ADDRESS", "0.0.0.0:8080"),
        num_runs=_read_int("FL_NUM_RUNS", 1),
        num_rounds=_read_int("FL_NUM_ROUNDS", 3),
        fraction_fit=_read_float("FL_FRACTION_FIT", 1.0),
        fraction_evaluate=_read_float("FL_FRACTION_EVALUATE", 1.0),
        min_available_clients=_read_int("FL_MIN_AVAILABLE_CLIENTS", 2),
        min_fit_clients=_read_int("FL_MIN_FIT_CLIENTS", 2),
        min_evaluate_clients=_read_int("FL_MIN_EVAL_CLIENTS", 2),
        learning_rate=_read_float("FL_LEARNING_RATE", 0.05),
        local_epochs=_read_int("FL_LOCAL_EPOCHS", 1),
        batch_size=_read_int("FL_BATCH_SIZE", 32),
        data_division=_read_str("FL_DATA_DIVISION", "iid"),
        dataset_path=_read_optional_str("FL_DATASET_PATH"),
        label_column=_read_str("FL_LABEL_COLUMN", "label"),
        test_split=_read_float("FL_TEST_SPLIT", 0.2),
        random_seed=_read_int("FL_RANDOM_SEED", 42),
        synthetic_samples=_read_int("FL_SYNTHETIC_SAMPLES", 1200),
        synthetic_features=_read_int("FL_SYNTHETIC_FEATURES", 8),
        results_dir=_read_str("FL_RESULTS_DIR", "results"),
        run_name=_read_str("FL_RUN_NAME", "experiment"),
        user_code_dir=_read_str("FL_USER_CODE_DIR", "/app/user_code"),
        user_entrypoint=_read_str("FL_USER_ENTRYPOINT", "server_logic.py:create_server_components"),
        user_requirements_path=_read_str("FL_USER_REQUIREMENTS_PATH", "requirements.txt"),
        install_user_requirements=_read_bool("FL_INSTALL_USER_REQUIREMENTS", True),
    )
    _validate_config(config)
    return config
