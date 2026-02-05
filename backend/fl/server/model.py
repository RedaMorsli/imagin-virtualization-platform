from __future__ import annotations

import numpy as np
from flwr.common import NDArrays


def initialize_parameters(num_features: int, seed: int) -> NDArrays:
    if num_features < 1:
        raise ValueError("Model must have at least one input feature")

    rng = np.random.default_rng(seed)
    weights = rng.normal(loc=0.0, scale=0.05, size=(num_features,)).astype(np.float32)
    bias = np.zeros((1,), dtype=np.float32)
    return [weights, bias]


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def evaluate_parameters(parameters: NDArrays, features: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    if len(parameters) != 2:
        raise ValueError("Expected exactly 2 model tensors: weights and bias")

    weights = np.asarray(parameters[0], dtype=np.float32).reshape(-1)
    bias = float(np.asarray(parameters[1], dtype=np.float32).reshape(-1)[0])

    if features.shape[1] != weights.shape[0]:
        raise ValueError(
            f"Model/dataset shape mismatch: got {features.shape[1]} features but {weights.shape[0]} weights"
        )

    logits = features @ weights + bias
    probabilities = _sigmoid(logits)

    eps = 1e-7
    probabilities = np.clip(probabilities, eps, 1.0 - eps)
    loss = -np.mean(labels * np.log(probabilities) + (1.0 - labels) * np.log(1.0 - probabilities))

    predictions = (probabilities >= 0.5).astype(np.float32)
    accuracy = float(np.mean(predictions == labels))
    return float(loss), accuracy

