"""Typed, run-bound capability negotiation for RuFLEX evidence operations."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ruflex.application.model_catalog import list_model_catalog
from ruflex.domain.training import TrainingRun


CapabilityKey = Literal[
    "occlusion",
    "shap",
    "tree_shap",
    "integrated_gradients",
    "gradient_shap",
    "exact_tree_path",
]


class CapabilityDecision(BaseModel):
    """One evidence operation evaluated against a persisted model run."""

    model_config = ConfigDict(extra="forbid")

    capability: CapabilityKey
    status: Literal["AVAILABLE", "NOT_APPLICABLE"]
    reason_code: Literal["AVAILABLE", "CAPABILITY_UNAVAILABLE"]
    detail: str


class RunCapabilityNegotiation(BaseModel):
    """Read-only compatibility evidence derived from the exact persisted run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    run_id: UUID
    model_kind: str
    model_artifact_sha256: str
    decisions: list[CapabilityDecision]
    scientific_note: str = (
        "This is a capability declaration for the persisted model artifact. "
        "AVAILABLE means RuFLEX has a compatible product-native route; it does not claim "
        "that post-hoc attribution is an exact or causal explanation."
    )


_CAPABILITY_ORDER: tuple[CapabilityKey, ...] = (
    "occlusion",
    "shap",
    "tree_shap",
    "integrated_gradients",
    "gradient_shap",
    "exact_tree_path",
)


def _catalog_key(run: TrainingRun) -> str:
    if run.model_kind in {"logistic_regression", "linear_regression"}:
        return "linear"
    return run.model_kind


def negotiate_run_capabilities(run: TrainingRun) -> RunCapabilityNegotiation:
    catalog = {entry["key"]: entry for entry in list_model_catalog()}
    entry = catalog.get(_catalog_key(run))
    capabilities = {} if entry is None else entry["capabilities"]
    label = run.model_kind.replace("_", " ")
    decisions: list[CapabilityDecision] = []
    for capability in _CAPABILITY_ORDER:
        if capabilities.get(capability, False):
            decisions.append(
                CapabilityDecision(
                    capability=capability,
                    status="AVAILABLE",
                    reason_code="AVAILABLE",
                    detail=f"The persisted {label} artifact declares {capability.replace('_', ' ')} support.",
                )
            )
        else:
            decisions.append(
                CapabilityDecision(
                    capability=capability,
                    status="NOT_APPLICABLE",
                    reason_code="CAPABILITY_UNAVAILABLE",
                    detail=f"The persisted {label} artifact does not declare a compatible {capability.replace('_', ' ')} route.",
                )
            )
    return RunCapabilityNegotiation(
        run_id=run.run_id,
        model_kind=run.model_kind,
        model_artifact_sha256=run.model_artifact_sha256,
        decisions=decisions,
    )
