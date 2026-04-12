from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ruflex.core.enums import NormalizationMode


@dataclass(frozen=True)
class DatasetConfig:
    target_column: str
    feature_columns: tuple[str, ...] | None = None
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    normalization: NormalizationMode = NormalizationMode.STANDARD
    fill_missing: str = "median"
    random_state: int = 42

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_column": self.target_column,
            "feature_columns": list(self.feature_columns) if self.feature_columns is not None else None,
            "validation_fraction": self.validation_fraction,
            "test_fraction": self.test_fraction,
            "normalization": self.normalization.value,
            "fill_missing": self.fill_missing,
            "random_state": self.random_state,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DatasetConfig":
        feature_columns = payload.get("feature_columns")
        return cls(
            target_column=payload["target_column"],
            feature_columns=None if feature_columns is None else tuple(feature_columns),
            validation_fraction=float(payload.get("validation_fraction", 0.2)),
            test_fraction=float(payload.get("test_fraction", 0.2)),
            normalization=NormalizationMode(payload.get("normalization", NormalizationMode.STANDARD.value)),
            fill_missing=payload.get("fill_missing", "median"),
            random_state=int(payload.get("random_state", 42)),
        )


@dataclass(frozen=True)
class NormalizationArtifact:
    mode: NormalizationMode
    feature_columns: tuple[str, ...]
    center: tuple[float, ...] | None = None
    scale: tuple[float, ...] | None = None
    minimum: tuple[float, ...] | None = None
    maximum: tuple[float, ...] | None = None

    def transform_array(self, values: np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=float)
        if self.mode is NormalizationMode.NONE:
            return array
        if self.mode is NormalizationMode.STANDARD:
            center = np.asarray(self.center, dtype=float)
            scale = np.asarray(self.scale, dtype=float)
            return (array - center) / np.where(scale == 0.0, 1.0, scale)
        minimum = np.asarray(self.minimum, dtype=float)
        maximum = np.asarray(self.maximum, dtype=float)
        span = np.where((maximum - minimum) == 0.0, 1.0, maximum - minimum)
        return (array - minimum) / span

    def transform_frame(self, frame: pd.DataFrame) -> np.ndarray:
        return self.transform_array(frame.loc[:, list(self.feature_columns)].to_numpy(dtype=float))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "feature_columns": list(self.feature_columns),
            "center": list(self.center) if self.center is not None else None,
            "scale": list(self.scale) if self.scale is not None else None,
            "minimum": list(self.minimum) if self.minimum is not None else None,
            "maximum": list(self.maximum) if self.maximum is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NormalizationArtifact":
        return cls(
            mode=NormalizationMode(payload["mode"]),
            feature_columns=tuple(payload["feature_columns"]),
            center=None if payload.get("center") is None else tuple(payload["center"]),
            scale=None if payload.get("scale") is None else tuple(payload["scale"]),
            minimum=None if payload.get("minimum") is None else tuple(payload["minimum"]),
            maximum=None if payload.get("maximum") is None else tuple(payload["maximum"]),
        )


@dataclass(frozen=True)
class DataSplit:
    feature_columns: tuple[str, ...]
    target_name: str
    train_features: np.ndarray
    train_targets: np.ndarray
    validation_features: np.ndarray
    validation_targets: np.ndarray
    test_features: np.ndarray
    test_targets: np.ndarray
    normalization: NormalizationArtifact


class TabularDataset:
    def __init__(
        self,
        frame: pd.DataFrame,
        source_path: str | None = None,
    ) -> None:
        self.frame = frame.copy()
        self.source_path = source_path

    @classmethod
    def from_csv(cls, path: str | Path) -> "TabularDataset":
        return cls(pd.read_csv(path), source_path=str(path))

    @classmethod
    def from_dataframe(cls, frame: pd.DataFrame) -> "TabularDataset":
        return cls(frame=frame, source_path=None)

    def numeric_feature_columns(self, target_column: str) -> tuple[str, ...]:
        numeric = self.frame.select_dtypes(include=[np.number]).columns.tolist()
        return tuple(column for column in numeric if column != target_column)

    def split(self, config: DatasetConfig) -> DataSplit:
        feature_columns = config.feature_columns or self.numeric_feature_columns(config.target_column)
        if not feature_columns:
            raise ValueError("No numeric feature columns were found for the dataset.")

        cleaned = self.frame.loc[:, list(feature_columns) + [config.target_column]].copy()
        if config.fill_missing == "median":
            for column in feature_columns:
                cleaned[column] = cleaned[column].fillna(cleaned[column].median())
        elif config.fill_missing == "drop":
            cleaned = cleaned.dropna()
        else:
            raise ValueError(f"Unsupported fill_missing mode: {config.fill_missing!r}.")

        cleaned = cleaned.dropna(subset=[config.target_column])
        features = cleaned.loc[:, list(feature_columns)].to_numpy(dtype=float)
        targets = cleaned.loc[:, config.target_column].to_numpy(dtype=float).reshape(-1, 1)

        test_fraction = float(config.test_fraction)
        validation_fraction = float(config.validation_fraction)
        if not 0.0 <= validation_fraction < 1.0:
            raise ValueError("validation_fraction must lie in [0, 1).")
        if not 0.0 <= test_fraction < 1.0:
            raise ValueError("test_fraction must lie in [0, 1).")
        if validation_fraction + test_fraction >= 1.0:
            raise ValueError("validation_fraction + test_fraction must be < 1.0.")

        train_features, test_features, train_targets, test_targets = train_test_split(
            features,
            targets,
            test_size=test_fraction,
            random_state=config.random_state,
        )

        effective_validation = validation_fraction / max(1.0 - test_fraction, 1e-12)
        if effective_validation > 0.0:
            train_features, validation_features, train_targets, validation_targets = train_test_split(
                train_features,
                train_targets,
                test_size=effective_validation,
                random_state=config.random_state,
            )
        else:
            validation_features = np.empty((0, len(feature_columns)), dtype=float)
            validation_targets = np.empty((0, 1), dtype=float)

        normalization = self._fit_normalization(train_features, feature_columns, config.normalization)
        return DataSplit(
            feature_columns=tuple(feature_columns),
            target_name=config.target_column,
            train_features=normalization.transform_array(train_features),
            train_targets=train_targets,
            validation_features=normalization.transform_array(validation_features),
            validation_targets=validation_targets,
            test_features=normalization.transform_array(test_features),
            test_targets=test_targets,
            normalization=normalization,
        )

    @staticmethod
    def _fit_normalization(
        train_features: np.ndarray,
        feature_columns: tuple[str, ...],
        mode: NormalizationMode,
    ) -> NormalizationArtifact:
        if mode is NormalizationMode.NONE:
            return NormalizationArtifact(mode=mode, feature_columns=feature_columns)
        if mode is NormalizationMode.STANDARD:
            center = tuple(float(value) for value in train_features.mean(axis=0))
            scale = tuple(float(value) for value in train_features.std(axis=0))
            return NormalizationArtifact(
                mode=mode,
                feature_columns=feature_columns,
                center=center,
                scale=scale,
            )
        return NormalizationArtifact(
            mode=mode,
            feature_columns=feature_columns,
            minimum=tuple(float(value) for value in train_features.min(axis=0)),
            maximum=tuple(float(value) for value in train_features.max(axis=0)),
        )

