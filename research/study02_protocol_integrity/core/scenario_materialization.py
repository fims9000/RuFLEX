"""Deterministically turn a frozen Study 02 plan into actual tabular product input."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScenarioExecutionInput:
    pair_id: str
    generator_family: str
    seed: int
    generator_parameters: dict
    frame: pd.DataFrame
    input_hash: str


def _fingerprint(frame: pd.DataFrame, *, pair_id: str, parameters: dict) -> str:
    payload = {
        "pair_id": pair_id,
        "parameters": parameters,
        "csv": frame.to_csv(index=False, float_format="%.17g"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def materialize_plan(plan: dict) -> ScenarioExecutionInput:
    """Materialize exactly the generator/seed/parameters stored in the plan."""
    params = dict(plan["generator_parameters"])
    seed = int(plan["seed"])
    if int(params["seed"]) != seed:
        raise ValueError("Frozen generator parameters do not bind the plan seed.")
    family = str(plan["generator_family"])
    if family != params["family"]:
        raise ValueError("Frozen generator family does not match its parameters.")
    count, features = int(params["sample_count"]), int(params["feature_count"])
    if count < 20 or features < 1:
        raise ValueError("Frozen scenario dimensions are invalid.")
    rng = np.random.default_rng(seed)
    values = rng.normal(0.0, 1.0, size=(count, features))
    if family == "temporal":
        values += np.linspace(0.0, float(params["temporal_drift"]), count)[:, None]
    if family == "grouped":
        group_count = int(params["group_count"])
        groups = np.arange(count) % group_count
        values += (groups[:, None] / max(group_count, 1)) * 0.15
    weights = rng.normal(0.0, 1.0, size=features)
    score = values @ weights + rng.normal(0.0, 0.15, size=count)
    positive_count = max(2, min(count - 2, int(round(count * float(params["class_imbalance"])))) )
    target = np.zeros(count, dtype=int); target[np.argsort(score)[-positive_count:]] = 1
    frame = pd.DataFrame(values, columns=[f"feature_{index + 1}" for index in range(features)])
    if family == "grouped": frame["group_id"] = groups
    if family == "temporal": frame["time_index"] = np.arange(count)
    frame["target"] = target
    return ScenarioExecutionInput(plan["pair_id"], family, seed, params, frame, _fingerprint(frame, pair_id=plan["pair_id"], parameters=params))
