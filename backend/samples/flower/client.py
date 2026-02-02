from __future__ import annotations

import torch
from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.client import ClientApp

from .task import Net, eval_one_client, load_data, train_one_client

app = ClientApp()


def _device() -> torch.device:
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


@app.train()
def train(msg: Message, context: Context) -> Message:
    """Train the model on this client's local partition."""
    # 1) Build model and load weights received from server
    model = Net()
    model.load_state_dict(msg.content["arrays"].to_torch_state_dict())

    # 2) Load local data partition (Flower provides these in simulation)
    partition_id = int(context.node_config["partition-id"])
    num_partitions = int(context.node_config["num-partitions"])
    batch_size = int(context.run_config["batch-size"])
    local_epochs = int(context.run_config["local-epochs"])
    lr = float(msg.content["config"]["lr"])  # sent by ServerApp

    trainloader, _ = load_data(partition_id, num_partitions, batch_size)

    # 3) Local training
    train_loss = train_one_client(model, trainloader, local_epochs, lr, _device())

    # 4) Reply with updated weights + metrics
    model_record = ArrayRecord(model.state_dict())
    metrics = {
        "train_loss": train_loss,
        "num-examples": len(trainloader.dataset),  # important for FedAvg weighting
    }
    metric_record = MetricRecord(metrics)

    content = RecordDict({"arrays": model_record, "metrics": metric_record})
    return Message(content=content, reply_to=msg)


@app.evaluate()
def evaluate(msg: Message, context: Context) -> Message:
    """Evaluate the current global model on this client's validation data."""
    model = Net()
    model.load_state_dict(msg.content["arrays"].to_torch_state_dict())

    partition_id = int(context.node_config["partition-id"])
    num_partitions = int(context.node_config["num-partitions"])
    batch_size = int(context.run_config["batch-size"])

    _, valloader = load_data(partition_id, num_partitions, batch_size)

    eval_loss, eval_acc = eval_one_client(model, valloader, _device())

    metrics = {
        "eval_loss": eval_loss,
        "eval_acc": eval_acc,
        "num-examples": len(valloader.dataset),
    }
    metric_record = MetricRecord(metrics)

    content = RecordDict({"metrics": metric_record})
    return Message(content=content, reply_to=msg)
