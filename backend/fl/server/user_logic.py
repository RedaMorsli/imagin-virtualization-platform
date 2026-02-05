from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import flwr as fl

from config import ExperimentConfig
from dataset import DatasetBundle


@dataclass(frozen=True)
class ServerRuntimeContext:
    config: ExperimentConfig
    config_dict: dict[str, Any]
    dataset: DatasetBundle
    run_index: int
    results_dir: Path


@dataclass(frozen=True)
class UserServerComponents:
    strategy: fl.server.strategy.Strategy
    server_config: fl.server.ServerConfig | None = None


def _resolve_requirements_path(config: ExperimentConfig, code_dir: Path) -> Path:
    req_path = Path(config.user_requirements_path)
    if not req_path.is_absolute():
        req_path = code_dir / req_path
    return req_path


def prepare_user_environment(config: ExperimentConfig) -> Path:
    code_dir = Path(config.user_code_dir)
    if not code_dir.exists() or not code_dir.is_dir():
        raise ValueError(f"FL_USER_CODE_DIR does not exist or is not a directory: {code_dir}")

    if str(code_dir) not in sys.path:
        sys.path.insert(0, str(code_dir))

    if config.install_user_requirements:
        requirements_path = _resolve_requirements_path(config, code_dir)
        if not requirements_path.exists() or not requirements_path.is_file():
            raise ValueError(f"User requirements file not found: {requirements_path}")

        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", str(requirements_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise RuntimeError(f"Failed to install user requirements: {detail}") from exc

    return code_dir


def _load_module_from_file(file_path: Path):
    module_name = f"user_server_logic_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_user_entrypoint(config: ExperimentConfig, code_dir: Path) -> Callable[[ServerRuntimeContext], Any]:
    module_ref, callable_name = config.user_entrypoint.split(":", 1)
    module_ref = module_ref.strip()
    callable_name = callable_name.strip()
    if not module_ref or not callable_name:
        raise ValueError("FL_USER_ENTRYPOINT must be in '<module_or_file>:<callable>' format")

    module = None
    candidate_path = Path(module_ref)
    if candidate_path.suffix == ".py":
        if not candidate_path.is_absolute():
            candidate_path = code_dir / candidate_path
        if not candidate_path.exists() or not candidate_path.is_file():
            raise ValueError(f"User entrypoint file does not exist: {candidate_path}")
        module = _load_module_from_file(candidate_path)
    else:
        module = importlib.import_module(module_ref)

    entrypoint = getattr(module, callable_name, None)
    if entrypoint is None or not callable(entrypoint):
        raise ValueError(f"Entrypoint callable was not found: {config.user_entrypoint}")

    return entrypoint


def resolve_user_server_components(
    components: Any,
    default_num_rounds: int,
) -> UserServerComponents:
    if isinstance(components, UserServerComponents):
        server_config = components.server_config or fl.server.ServerConfig(num_rounds=default_num_rounds)
        return UserServerComponents(strategy=components.strategy, server_config=server_config)

    if isinstance(components, tuple) and len(components) == 2:
        strategy, server_config = components
        if not isinstance(strategy, fl.server.strategy.Strategy):
            raise TypeError("Entrypoint tuple[0] must be a Flower strategy instance")
        if server_config is None:
            server_config = fl.server.ServerConfig(num_rounds=default_num_rounds)
        if not isinstance(server_config, fl.server.ServerConfig):
            raise TypeError("Entrypoint tuple[1] must be fl.server.ServerConfig or None")
        return UserServerComponents(strategy=strategy, server_config=server_config)

    if isinstance(components, fl.server.strategy.Strategy):
        return UserServerComponents(
            strategy=components,
            server_config=fl.server.ServerConfig(num_rounds=default_num_rounds),
        )

    raise TypeError(
        "Entrypoint must return a Strategy, UserServerComponents, or (Strategy, ServerConfig) tuple"
    )


def build_runtime_context(
    config: ExperimentConfig,
    dataset: DatasetBundle,
    run_index: int,
) -> ServerRuntimeContext:
    return ServerRuntimeContext(
        config=config,
        config_dict=asdict(config),
        dataset=dataset,
        run_index=run_index,
        results_dir=Path(config.results_dir),
    )
