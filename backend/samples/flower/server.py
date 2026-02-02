from __future__ import annotations

import torch
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord
from flwr.server import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg

from .task import Net, eval_one_client, load_data

app = ServerApp()


def global_evaluate(server_round: int, arrays: ArrayRecord) -> MetricRecord | None:
    """Optional centralized eval on a server-side dataset."""
    model = Net()
    model.load_state_dict(arrays.to_torch_state_dict())

    # Central validation set (synthetic, fixed)
    _, valloader = load_data(partition_id=0, num_partitions=1, batch_size=256)
    loss, acc = eval_one_client(model, valloader, device=torch.device("cpu"))

    return MetricRecord({"global_loss": loss, "global_acc": acc})


@app.main()
def main(grid: Grid, context: Context) -> None:
    # Read run config from pyproject.toml
    num_rounds = int(context.run_config["num-server-rounds"])
    lr = float(context.run_config["learning-rate"])
    fraction_train = float(context.run_config["fraction-train"])
    fraction_evaluate = float(context.run_config["fraction-evaluate"])

    # Initial global model
    global_model = Net()
    arrays = ArrayRecord(global_model.state_dict())

    # FedAvg strategy (weights by "num-examples" by default)
    strategy = FedAvg(
        fraction_train=fraction_train,
        fraction_evaluate=fraction_evaluate,
    )

    # Start the FL loop
    result = strategy.start(
        grid=grid,
        initial_arrays=arrays,
        num_rounds=num_rounds,
        train_config=ConfigRecord({"lr": lr}),
        evaluate_fn=global_evaluate,
    )

    # Save final model
    state_dict = result.arrays.to_torch_state_dict()
    torch.save(state_dict, "final_model.pt")
    print("Saved: final_model.pt")
