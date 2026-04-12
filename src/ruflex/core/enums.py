from __future__ import annotations

from enum import Enum


class TaskType(str, Enum):
    REGRESSION = "regression"
    BINARY_CLASSIFICATION = "binary_classification"


class VariableRole(str, Enum):
    INPUT = "input"
    HIDDEN_CONCEPT = "hidden_concept"
    OUTPUT = "output"


class NormalizationMode(str, Enum):
    NONE = "none"
    STANDARD = "standard"
    MINMAX = "minmax"


class MembershipKind(str, Enum):
    GAUSSIAN = "gaussian"
    GENERALIZED_BELL = "generalized_bell"
    TRIANGULAR = "triangular"
    TRAPEZOIDAL = "trapezoidal"

