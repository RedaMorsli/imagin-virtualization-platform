"""
federated_mnist_fedavg.py
=========================
Self-contained Federated Learning demo using:
  - Flower (flwr) simulation API
  - FedAvg aggregation strategy
  - MNIST dataset (auto-downloaded via torchvision)
  - CNN architecture consistent with the research codebase (MNISTModel)

Install dependencies (once):
    pip install torch torchvision
    pip install -U "flwr[simulation]"


Run:
    python federated_mnist_fedavg.py
"""

import copy
import warnings
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

import flwr as fl
from flwr.common import (
    NDArrays,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.server.strategy import FedAvg

warnings.filterwarnings("ignore", category=UserWarning)

# ─────────────────────────────────────────────
# 0.  CONFIGURATION  (edit these freely)
# ─────────────────────────────────────────────
CONFIG = {
    "num_clients": 5,           # total number of simulated clients
    "num_rounds": 10,           # federated communication rounds
    "local_epochs": 2,          # local training epochs per round
    "batch_size": 32,
    "lr": 0.01,
    "fraction_fit": 1.0,        # fraction of clients selected each round
    "fraction_evaluate": 1.0,
    "min_fit_clients": 2,
    "min_evaluate_clients": 2,
    "min_available_clients": 2,
    "seed": 42,
}

torch.manual_seed(CONFIG["seed"])
np.random.seed(CONFIG["seed"])
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[INFO] Using device: {DEVICE}")


# ─────────────────────────────────────────────
# 1.  MODEL  (mirrors MNISTModel in the codebase)
# ─────────────────────────────────────────────
class MNISTModel(nn.Module):
    """
    Conv-based MNIST classifier.
    Architecture matches fall_models/mnist_models.py::MNISTModel.
    Input:  (batch, 1, 28, 28)
    Output: (batch, 10)
    """
    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, kernel_size=5)   # → 16×24×24
        self.pool  = nn.MaxPool2d(2, 2)                # → 16×12×12
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5)  # → 32×8×8  (after pool: 32×4×4)
        self.fc1   = nn.Linear(32 * 4 * 4, 120)
        self.fc2   = nn.Linear(120, 84)
        self.fc3   = nn.Linear(84, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


# ─────────────────────────────────────────────
# 2.  DATA LOADING  (auto-downloads MNIST)
# ─────────────────────────────────────────────
def load_datasets(num_clients: int):
    """
    Download MNIST and split the training set across `num_clients`
    using a uniform IID partition (consistent with PercentageRandomDistributor).
    Returns a list of per-client DataLoaders and one global test DataLoader.
    """
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])

    train_full = datasets.MNIST(
        root="./data", train=True, download=True, transform=transform
    )
    test_set = datasets.MNIST(
        root="./data", train=False, download=True, transform=transform
    )

    # IID split: shuffle indices then divide equally
    indices = torch.randperm(len(train_full), generator=torch.Generator().manual_seed(CONFIG["seed"])).tolist()
    split_size = len(indices) // num_clients
    client_loaders = []
    for i in range(num_clients):
        start = i * split_size
        end   = start + split_size if i < num_clients - 1 else len(indices)
        subset = Subset(train_full, indices[start:end])
        loader = DataLoader(subset, batch_size=CONFIG["batch_size"], shuffle=True)
        client_loaders.append(loader)

    test_loader = DataLoader(test_set, batch_size=64, shuffle=False)
    return client_loaders, test_loader


# ─────────────────────────────────────────────
# 3.  LOCAL TRAINING & EVALUATION HELPERS
# ─────────────────────────────────────────────
def train(
    model: nn.Module,
    loader: DataLoader,
    epochs: int,
    lr: float,
    device: torch.device,
) -> Tuple[float, int]:
    """Run local SGD training. Returns (avg_loss, num_samples)."""
    model.to(device)
    model.train()
    optimizer  = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    criterion  = nn.CrossEntropyLoss()
    total_loss = 0.0
    n_samples  = 0

    for _ in range(epochs):
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * labels.size(0)
            n_samples  += labels.size(0)

    avg_loss = total_loss / n_samples if n_samples > 0 else 0.0
    return avg_loss, n_samples


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> Tuple[float, float, int]:
    """Evaluate model. Returns (loss, accuracy, num_samples)."""
    model.to(device)
    model.eval()
    criterion  = nn.CrossEntropyLoss()
    total_loss = 0.0
    correct    = 0
    n_samples  = 0

    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            total_loss += criterion(outputs, labels).item() * labels.size(0)
            correct    += outputs.argmax(1).eq(labels).sum().item()
            n_samples  += labels.size(0)

    loss     = total_loss / n_samples
    accuracy = correct   / n_samples
    return loss, accuracy, n_samples


# ─────────────────────────────────────────────
# 4.  MODEL WEIGHT HELPERS  (NDArrays ↔ state_dict)
# ─────────────────────────────────────────────
def get_weights(model: nn.Module) -> NDArrays:
    return [val.cpu().numpy() for val in model.state_dict().values()]


def set_weights(model: nn.Module, weights: NDArrays) -> None:
    state_dict = OrderedDict(
        {k: torch.tensor(v) for k, v in zip(model.state_dict().keys(), weights)}
    )
    model.load_state_dict(state_dict, strict=True)


# ─────────────────────────────────────────────
# 5.  FLOWER CLIENT
# ─────────────────────────────────────────────
class FlowerClient(fl.client.NumPyClient):
    """
    Flower NumPyClient.
    Each instance holds its own model replica and a local DataLoader,
    mirroring the Client/Trainer pattern in the research codebase.
    """

    def __init__(self, client_id: int, train_loader: DataLoader, test_loader: DataLoader):
        self.client_id    = client_id
        self.train_loader = train_loader
        self.test_loader  = test_loader
        self.model        = MNISTModel().to(DEVICE)

    # Called by Flower server to pull the current local weights
    def get_parameters(self, config: Dict[str, Scalar]) -> NDArrays:
        return get_weights(self.model)

    # Called each round: receive global weights → local train → return updated weights
    def fit(
        self,
        parameters: NDArrays,
        config: Dict[str, Scalar],
    ) -> Tuple[NDArrays, int, Dict[str, Scalar]]:
        # 1. Load the global model weights
        set_weights(self.model, parameters)

        # 2. Local training (mirrors Trainer.train in trainer.py)
        epochs = int(config.get("local_epochs", CONFIG["local_epochs"]))
        lr     = float(config.get("lr", CONFIG["lr"]))
        avg_loss, n_samples = train(self.model, self.train_loader, epochs, lr, DEVICE)

        print(
            f"  [Client {self.client_id}] "
            f"trained on {n_samples} samples | local_loss={avg_loss:.4f}"
        )
        return get_weights(self.model), n_samples, {"loss": avg_loss}

    # Called by Flower to evaluate the current global model on local data
    def evaluate(
        self,
        parameters: NDArrays,
        config: Dict[str, Scalar],
    ) -> Tuple[float, int, Dict[str, Scalar]]:
        set_weights(self.model, parameters)
        loss, accuracy, n_samples = evaluate(self.model, self.test_loader, DEVICE)
        return float(loss), n_samples, {"accuracy": float(accuracy)}


# ─────────────────────────────────────────────
# 6.  SERVER-SIDE EVALUATION (centralised)
# ─────────────────────────────────────────────
def build_server_eval_fn(
    test_loader: DataLoader,
):
    """
    Returns a server-side evaluation function that Flower calls after every
    aggregation round — mirrors the infer() calls in fl_server.py.
    """
    def evaluate_fn(
        server_round: int,
        parameters: NDArrays,
        config: Dict[str, Scalar],
    ) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        model = MNISTModel().to(DEVICE)
        set_weights(model, parameters)
        loss, accuracy, _ = evaluate(model, test_loader, DEVICE)
        print(
            f"\n[Server] Round {server_round} | "
            f"loss={loss:.4f} | accuracy={accuracy:.4f}\n"
        )
        return loss, {"accuracy": accuracy}

    return evaluate_fn


# ─────────────────────────────────────────────
# 7.  FedAvg STRATEGY  (mirrors fl_server.py aggregate logic)
# ─────────────────────────────────────────────
def build_strategy(initial_params, test_loader: DataLoader) -> FedAvg:
    """
    Wrap Flower's built-in FedAvg with:
      - server-side centralised evaluation
      - per-round config injection (local_epochs, lr)
    """
    return FedAvg(
        fraction_fit          = CONFIG["fraction_fit"],
        fraction_evaluate     = CONFIG["fraction_evaluate"],
        min_fit_clients       = CONFIG["min_fit_clients"],
        min_evaluate_clients  = CONFIG["min_evaluate_clients"],
        min_available_clients = CONFIG["min_available_clients"],
        initial_parameters    = ndarrays_to_parameters(initial_params),
        evaluate_fn           = build_server_eval_fn(test_loader),
        on_fit_config_fn      = lambda rnd: {
            "local_epochs": CONFIG["local_epochs"],
            "lr": CONFIG["lr"],
        },
    )


# ─────────────────────────────────────────────
# 8.  CLIENT FACTORY  (used by Flower simulation)
# ─────────────────────────────────────────────
def make_client_fn(client_loaders: List[DataLoader], test_loader: DataLoader):
    """
    Returns a closure that Flower's simulation engine calls to
    instantiate each virtual client by its string ID.
    """
    def client_fn(cid: str) -> fl.client.Client:
        idx = int(cid)
        return FlowerClient(
            client_id    = idx,
            train_loader = client_loaders[idx],
            test_loader  = test_loader,
        ).to_client()

    return client_fn


# ─────────────────────────────────────────────
# 9.  ENTRY POINT
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Federated Learning — FedAvg on MNIST (Flower simulation)")
    print("=" * 60)
    print(f"  Clients      : {CONFIG['num_clients']}")
    print(f"  Rounds       : {CONFIG['num_rounds']}")
    print(f"  Local epochs : {CONFIG['local_epochs']}")
    print(f"  Batch size   : {CONFIG['batch_size']}")
    print(f"  Learning rate: {CONFIG['lr']}")
    print("=" * 60)

    # Load data
    client_loaders, test_loader = load_datasets(CONFIG["num_clients"])

    # Initial global model weights (broadcast to all clients in round 0)
    global_model    = MNISTModel()
    initial_weights = get_weights(global_model)

    # Build strategy and client factory
    strategy   = build_strategy(initial_weights, test_loader)
    client_fn  = make_client_fn(client_loaders, test_loader)

    # Run simulation (all clients live in the same process — no ports needed)
    history = fl.simulation.start_simulation(
        client_fn         = client_fn,
        num_clients       = CONFIG["num_clients"],
        config            = fl.server.ServerConfig(num_rounds=CONFIG["num_rounds"]),
        strategy          = strategy,
        client_resources  = {"num_cpus": 1, "num_gpus": 0.0},
    )

    # ── Final summary ──────────────────────────────
    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE — Final Results")
    print("=" * 60)

    if history.losses_centralized:
        final_loss = history.losses_centralized[-1][1]
        print(f"  Final centralised loss     : {final_loss:.4f}")

    if history.metrics_centralized:
        accs = history.metrics_centralized.get("accuracy", [])
        if accs:
            final_acc = accs[-1][1]
            print(f"  Final centralised accuracy : {final_acc:.4f} ({final_acc*100:.2f}%)")

    print("\n  Per-round accuracy:")
    for rnd, acc in history.metrics_centralized.get("accuracy", []):
        print(f"    Round {rnd:>2}: {acc:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()