"""
FL Client — runs inside a Docker container, one per simulated client.

Trains a CNN on a local IID shard of MNIST and participates in FedAvg.

Environment variables:
    CLIENT_ID       zero-based index of this client (default 0)
    FL_NUM_CLIENTS  total number of clients, used for data partitioning (default 2)
    SERVER_HOST     hostname of the Flower server container (default server)
    SERVER_PORT     gRPC port of the Flower server (default 8080)
    METRIC_LOGGING  "local" or "wandb" (default "local")
    WANDB_API_KEY   W&B API key (required when METRIC_LOGGING=wandb)
    WANDB_ENTITY    W&B entity / team name (optional)
    WANDB_PROJECT   W&B project name
    WANDB_RUN_NAME  W&B run name (will be suffixed with client id)
"""

import os
from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
import flwr as fl

CLIENT_ID      = int(os.environ.get("CLIENT_ID", "0"))
NUM_CLIENTS    = int(os.environ.get("FL_NUM_CLIENTS", "2"))
SERVER_HOST    = os.environ.get("SERVER_HOST", "server")
SERVER_PORT    = int(os.environ.get("SERVER_PORT", "8080"))
METRIC_LOGGING = os.environ.get("METRIC_LOGGING", "local")
WANDB_API_KEY  = os.environ.get("WANDB_API_KEY", "")
WANDB_ENTITY   = os.environ.get("WANDB_ENTITY", "") or None
WANDB_PROJECT  = os.environ.get("WANDB_PROJECT", "fl-platform")
WANDB_RUN_NAME = os.environ.get("WANDB_RUN_NAME", "run")

DEVICE = torch.device("cpu")

print(f"[client-{CLIENT_ID}] num_clients={NUM_CLIENTS} server={SERVER_HOST}:{SERVER_PORT}")
print(f"[client-{CLIENT_ID}] metric_logging={METRIC_LOGGING}")

_wandb_run = None

if METRIC_LOGGING == "wandb":
    if not WANDB_API_KEY:
        print(f"[client-{CLIENT_ID}] warn: METRIC_LOGGING=wandb but WANDB_API_KEY is empty — skipping wandb")
    else:
        print(f"[client-{CLIENT_ID}] initialising wandb entity='{WANDB_ENTITY}' project='{WANDB_PROJECT}' run='{WANDB_RUN_NAME}-client-{CLIENT_ID}'")
        try:
            import wandb
            wandb.login(key=WANDB_API_KEY)
            _wandb_run = wandb.init(
                entity=WANDB_ENTITY,
                project=WANDB_PROJECT,
                name=f"{WANDB_RUN_NAME}-client-{CLIENT_ID}",
                group=WANDB_RUN_NAME,
                config={
                    "client_id":   CLIENT_ID,
                    "num_clients": NUM_CLIENTS,
                    "role":        "client",
                },
            )
            print(f"[client-{CLIENT_ID}] wandb run initialised: {_wandb_run.url}")
        except Exception as exc:
            print(f"[client-{CLIENT_ID}] warn: wandb init failed: {exc}")
            _wandb_run = None
else:
    print(f"[client-{CLIENT_ID}] metric_logging=local, wandb disabled")


# ── Model ─────────────────────────────────────────────────────────────────────

class MNISTModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, kernel_size=5)
        self.pool  = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5)
        self.fc1   = nn.Linear(32 * 4 * 4, 120)
        self.fc2   = nn.Linear(120, 84)
        self.fc3   = nn.Linear(84, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


# ── Data ──────────────────────────────────────────────────────────────────────

def load_data():
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    train_full = datasets.MNIST("./data", train=True,  download=True, transform=transform)
    test_set   = datasets.MNIST("./data", train=False, download=True, transform=transform)

    indices   = list(range(len(train_full)))
    shard_sz  = len(indices) // NUM_CLIENTS
    start     = CLIENT_ID * shard_sz
    end       = start + shard_sz if CLIENT_ID < NUM_CLIENTS - 1 else len(indices)

    train_loader = DataLoader(Subset(train_full, indices[start:end]), batch_size=32, shuffle=True)
    test_loader  = DataLoader(test_set, batch_size=64, shuffle=False)
    return train_loader, test_loader


# ── Weight helpers ─────────────────────────────────────────────────────────────

def get_weights(model: nn.Module):
    return [val.cpu().numpy() for val in model.state_dict().values()]


def set_weights(model: nn.Module, weights) -> None:
    state = OrderedDict(
        {k: torch.tensor(v) for k, v in zip(model.state_dict().keys(), weights)}
    )
    model.load_state_dict(state, strict=True)


# ── Flower client ──────────────────────────────────────────────────────────────

class MNISTClient(fl.client.NumPyClient):
    def __init__(self):
        self.model        = MNISTModel().to(DEVICE)
        self.train_loader, self.test_loader = load_data()

    def get_parameters(self, config):
        return get_weights(self.model)

    def fit(self, parameters, config):
        set_weights(self.model, parameters)
        server_round  = int(config.get("server_round", 1))
        epochs        = int(config.get("local_epochs", "1"))
        optimizer     = torch.optim.SGD(self.model.parameters(), lr=0.01, momentum=0.9)
        criterion     = nn.CrossEntropyLoss()
        self.model.train()
        total_loss, n_samples = 0.0, 0
        for _ in range(epochs):
            for images, labels in self.train_loader:
                images, labels = images.to(DEVICE), labels.to(DEVICE)
                optimizer.zero_grad()
                loss = criterion(self.model(images), labels)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * labels.size(0)
                n_samples  += labels.size(0)

        train_loss = total_loss / n_samples if n_samples > 0 else 0.0
        print(f"[client-{CLIENT_ID}] round {server_round} fit — train_loss={train_loss:.4f} samples={n_samples}")

        if _wandb_run is not None:
            try:
                _wandb_run.log({"client/train_loss": train_loss}, step=server_round)
            except Exception as exc:
                print(f"[client-{CLIENT_ID}] warn: wandb.log failed: {exc}")

        # Return train_loss and client_id in metrics so the server can aggregate and map clients
        return get_weights(self.model), n_samples, {"train_loss": train_loss, "client_id": CLIENT_ID}

    def evaluate(self, parameters, config):
        set_weights(self.model, parameters)
        server_round = int(config.get("server_round", 1))
        criterion    = nn.CrossEntropyLoss()
        self.model.eval()
        total_loss, correct, n = 0.0, 0, 0
        with torch.no_grad():
            for images, labels in self.test_loader:
                images, labels = images.to(DEVICE), labels.to(DEVICE)
                outputs     = self.model(images)
                total_loss += criterion(outputs, labels).item() * labels.size(0)
                correct    += outputs.argmax(1).eq(labels).sum().item()
                n          += labels.size(0)

        eval_loss     = float(total_loss / n)
        eval_accuracy = float(correct / n)
        print(f"[client-{CLIENT_ID}] round {server_round} eval — loss={eval_loss:.4f} accuracy={eval_accuracy:.4f}")

        if _wandb_run is not None:
            try:
                _wandb_run.log(
                    {
                        "client/eval_loss":     eval_loss,
                        "client/eval_accuracy": eval_accuracy,
                    },
                    step=server_round,
                )
            except Exception as exc:
                print(f"[client-{CLIENT_ID}] warn: wandb.log failed: {exc}")

        return eval_loss, n, {"accuracy": eval_accuracy}


fl.client.start_client(
    server_address=f"{SERVER_HOST}:{SERVER_PORT}",
    client=MNISTClient().to_client(),
)

if _wandb_run is not None:
    try:
        _wandb_run.finish()
        print(f"[client-{CLIENT_ID}] wandb run finished")
    except Exception:
        pass
