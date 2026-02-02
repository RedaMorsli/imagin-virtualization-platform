from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset


class Net(torch.nn.Module):
    """Tiny binary classifier: R^2 -> R (logit)."""

    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x).squeeze(1)  # (B,)


def make_synthetic_dataset(
    partition_id: int,
    num_partitions: int,
    n_samples: int = 1200,
) -> tuple[np.ndarray, np.ndarray]:
    """Create slightly different data distributions per client."""
    rng = np.random.default_rng(seed=1234 + partition_id)

    # Shift each client's feature distribution a bit (non-iid-ish)
    shift = (partition_id - (num_partitions - 1) / 2.0) * 0.6
    x = rng.normal(loc=shift, scale=1.0, size=(n_samples, 2)).astype(np.float32)

    # Linear boundary + noise
    w = np.array([1.2, -0.7], dtype=np.float32)
    b = -0.1 + 0.2 * shift
    logits = x @ w + b + rng.normal(scale=0.2, size=n_samples).astype(np.float32)
    y = (logits > 0).astype(np.float32)  # 0/1 floats for BCE

    return x, y


def load_data(
    partition_id: int,
    num_partitions: int,
    batch_size: int,
) -> tuple[DataLoader, DataLoader]:
    x, y = make_synthetic_dataset(partition_id, num_partitions)

    split = int(0.8 * len(x))
    x_train, y_train = x[:split], y[:split]
    x_val, y_val = x[split:], y[split:]

    train_ds = TensorDataset(torch.from_numpy(x_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(x_val), torch.from_numpy(y_val))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    return train_loader, val_loader


def train_one_client(
    model: torch.nn.Module,
    trainloader: DataLoader,
    epochs: int,
    lr: float,
    device: torch.device,
) -> float:
    model.train()
    model.to(device)

    opt = torch.optim.SGD(model.parameters(), lr=lr)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    total_loss = 0.0
    total = 0

    for _ in range(epochs):
        for xb, yb in trainloader:
            xb, yb = xb.to(device), yb.to(device)

            opt.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()

            bs = xb.size(0)
            total_loss += float(loss.item()) * bs
            total += bs

    return total_loss / max(total, 1)


@torch.no_grad()
def eval_one_client(
    model: torch.nn.Module,
    valloader: DataLoader,
    device: torch.device,
) -> tuple[float, float]:
    model.eval()
    model.to(device)

    loss_fn = torch.nn.BCEWithLogitsLoss()

    total_loss = 0.0
    total = 0
    correct = 0

    for xb, yb in valloader:
        xb, yb = xb.to(device), yb.to(device)

        logits = model(xb)
        loss = loss_fn(logits, yb)

        probs = torch.sigmoid(logits)
        preds = (probs > 0.5).float()
        correct += int((preds == yb).sum().item())

        bs = xb.size(0)
        total_loss += float(loss.item()) * bs
        total += bs

    return total_loss / max(total, 1), correct / max(total, 1)
