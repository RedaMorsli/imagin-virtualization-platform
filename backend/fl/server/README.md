# Flower FL Server

This folder contains a container-ready Flower server runtime that handles experiment orchestration, while user-supplied Python code defines the FL server logic (strategy, evaluation, client selection behavior).

## Included files

- `server.py`: Runtime entrypoint that loads user logic, runs experiments, and exports metrics.
- `config.py`: Reads and validates experiment settings from environment variables.
- `dataset.py`: Loads a CSV dataset or generates synthetic binary data.
- `user_logic.py`: Loads user files, installs user requirements, and resolves server components.
- `model.py`: Optional helper utilities for simple baseline model initialization/evaluation.
- `Dockerfile`: Builds the FL server container image.
- `requirements.txt`: Python dependencies for the image.

## Supported environment variables

- `FL_SERVER_ADDRESS` (default: `0.0.0.0:8080`)
- `FL_NUM_RUNS` (default: `1`)
- `FL_NUM_ROUNDS` (default: `3`)
- `FL_MIN_AVAILABLE_CLIENTS` (default: `2`)
- `FL_MIN_FIT_CLIENTS` (default: `2`)
- `FL_MIN_EVAL_CLIENTS` (default: `2`)
- `FL_FRACTION_FIT` (default: `1.0`)
- `FL_FRACTION_EVALUATE` (default: `1.0`)
- `FL_LEARNING_RATE` (default: `0.05`) - sent to clients
- `FL_LOCAL_EPOCHS` (default: `1`) - sent to clients
- `FL_BATCH_SIZE` (default: `32`) - sent to clients
- `FL_DATA_DIVISION` (default: `iid`) - sent to clients
- `FL_DATASET_PATH` (optional) - CSV file path in container
- `FL_LABEL_COLUMN` (default: `label`) - label column in CSV
- `FL_TEST_SPLIT` (default: `0.2`)
- `FL_RANDOM_SEED` (default: `42`)
- `FL_SYNTHETIC_SAMPLES` (default: `1200`) - used when no CSV is provided
- `FL_SYNTHETIC_FEATURES` (default: `8`) - used when no CSV is provided
- `FL_RESULTS_DIR` (default: `results`)
- `FL_RUN_NAME` (default: `experiment`)
- `FL_USER_CODE_DIR` (default: `/app/user_code`) - mounted user server code folder
- `FL_USER_ENTRYPOINT` (default: `server_logic.py:create_server_components`)
- `FL_USER_REQUIREMENTS_PATH` (default: `requirements.txt`) - relative to `FL_USER_CODE_DIR` unless absolute
- `FL_INSTALL_USER_REQUIREMENTS` (default: `true`)

## User logic contract

Entrypoint callable receives `ServerRuntimeContext` (from `user_logic.py`) and must return one of:

- a Flower `Strategy`
- `UserServerComponents(strategy=..., server_config=...)`
- `(strategy, server_config)` tuple

`server_config` can be `None` to use `FL_NUM_ROUNDS`.

Minimal user file (`/app/user_code/server_logic.py`):

```python
import flwr as fl
from user_logic import UserServerComponents

def create_server_components(ctx):
    strategy = fl.server.strategy.FedAvg(
        min_available_clients=ctx.config.min_available_clients,
        min_fit_clients=ctx.config.min_fit_clients,
        min_evaluate_clients=ctx.config.min_evaluate_clients,
        fraction_fit=ctx.config.fraction_fit,
        fraction_evaluate=ctx.config.fraction_evaluate,
    )
    return UserServerComponents(strategy=strategy, server_config=None)
```

## Run locally

```bash
pip install -r fl/server/requirements.txt
set FL_USER_CODE_DIR=fl/user_code
set FL_USER_ENTRYPOINT=server_logic.py:create_server_components
python fl/server/server.py
```

## Build image

```bash
docker build -f fl/server/Dockerfile -t fl-server:latest .
```
