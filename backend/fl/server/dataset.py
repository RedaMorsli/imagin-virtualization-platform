from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from config import ExperimentConfig


@dataclass(frozen=True)
class DatasetBundle:
    train_x: np.ndarray
    train_y: np.ndarray
    test_x: np.ndarray
    test_y: np.ndarray


def _encode_labels(raw_labels: list[str]) -> np.ndarray:
    try:
        labels = np.asarray([float(item) for item in raw_labels], dtype=np.float32)
    except ValueError:
        unique_labels = sorted(set(raw_labels))
        if len(unique_labels) != 2:
            raise ValueError("Dataset labels must contain exactly two classes for binary classification")
        mapping = {unique_labels[0]: 0.0, unique_labels[1]: 1.0}
        labels = np.asarray([mapping[item] for item in raw_labels], dtype=np.float32)
        return labels

    unique_values = np.unique(labels)
    if len(unique_values) < 2:
        raise ValueError("Dataset labels must contain at least two classes")
    if len(unique_values) > 2:
        raise ValueError("Dataset labels must contain at most two classes")

    min_label = float(np.min(unique_values))
    max_label = float(np.max(unique_values))
    if min_label == 0.0 and max_label == 1.0:
        return labels

    return np.where(labels == min_label, 0.0, 1.0).astype(np.float32)


def _load_csv_dataset(path: Path, label_column: str) -> tuple[np.ndarray, np.ndarray]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if label_column not in fieldnames:
            raise ValueError(f"Label column '{label_column}' was not found in dataset")

        feature_columns = [name for name in fieldnames if name != label_column]
        if not feature_columns:
            raise ValueError("Dataset must include at least one feature column")

        features: list[list[float]] = []
        labels: list[str] = []
        for line_no, row in enumerate(reader, start=2):
            try:
                feature_row = [float(row[column_name]) for column_name in feature_columns]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric feature value at CSV line {line_no}") from exc

            label_value = row.get(label_column, "")
            if label_value is None or str(label_value).strip() == "":
                raise ValueError(f"Missing label value at CSV line {line_no}")

            features.append(feature_row)
            labels.append(str(label_value))

    if not features:
        raise ValueError("Dataset CSV is empty")

    feature_array = np.asarray(features, dtype=np.float32)
    label_array = _encode_labels(labels)
    return feature_array, label_array


def _generate_synthetic_dataset(
    num_samples: int,
    num_features: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    features = rng.normal(loc=0.0, scale=1.0, size=(num_samples, num_features)).astype(np.float32)
    coefficients = rng.normal(loc=0.0, scale=1.0, size=(num_features,))
    logits = features @ coefficients + rng.normal(loc=0.0, scale=0.4, size=(num_samples,))
    labels = (logits > 0.0).astype(np.float32)
    return features, labels


def _train_test_split(
    features: np.ndarray,
    labels: np.ndarray,
    test_split: float,
    seed: int,
) -> DatasetBundle:
    if features.shape[0] != labels.shape[0]:
        raise ValueError("Feature/label sample counts do not match")
    if features.shape[0] < 2:
        raise ValueError("Dataset must contain at least two rows")

    rng = np.random.default_rng(seed)
    indices = rng.permutation(features.shape[0])
    test_size = int(round(features.shape[0] * test_split))
    test_size = max(1, min(features.shape[0] - 1, test_size))

    test_indices = indices[:test_size]
    train_indices = indices[test_size:]

    return DatasetBundle(
        train_x=features[train_indices],
        train_y=labels[train_indices],
        test_x=features[test_indices],
        test_y=labels[test_indices],
    )


def load_dataset(config: ExperimentConfig) -> DatasetBundle:
    if config.dataset_path:
        dataset_path = Path(config.dataset_path)
        if not dataset_path.is_file():
            raise ValueError(f"Dataset path does not exist: {dataset_path}")
        features, labels = _load_csv_dataset(dataset_path, config.label_column)
    else:
        features, labels = _generate_synthetic_dataset(
            num_samples=config.synthetic_samples,
            num_features=config.synthetic_features,
            seed=config.random_seed,
        )

    return _train_test_split(
        features=features,
        labels=labels,
        test_split=config.test_split,
        seed=config.random_seed,
    )

