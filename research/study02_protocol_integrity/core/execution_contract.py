"""Frozen, oracle-free contracts for Study 02 product execution attempts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal


PRODUCT_SHA256 = "772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224"
Outcome = Literal[
    "PREVENTED_STRUCTURALLY", "PREVENTED_BY_FIREWALL", "DETECTED_AFTER_IMPORT",
    "ALLOWED_VALID", "MISSED", "NOT_APPLICABLE", "EXECUTION_ERROR",
]


@dataclass(frozen=True)
class ExecutionAttemptContract:
    study_revision: str
    pair_id: str
    scenario_id: str
    violation_family: str
    clean_or_corrupt: Literal["clean", "corrupt"]
    product_sha: str
    expected_product_entrypoint: str
    operation_role: str
    data_roles: tuple[str, ...]
    allowed_source_roles: tuple[str, ...]
    forbidden_source_roles: tuple[str, ...]
    artifact_type_expected: str
    expected_semantic_outcome: Outcome
    persistence_required: bool
    oracle_reference_id: str
    generator_family: str
    generator_parameters: dict
    seed: int
    base_input_hash: str

    def payload(self) -> dict:
        return asdict(self)

    @property
    def contract_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.payload(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @classmethod
    def from_payload(cls, value: dict) -> "ExecutionAttemptContract":
        for key in ("data_roles", "allowed_source_roles", "forbidden_source_roles"):
            value[key] = tuple(value[key])
        return cls(**value)


def contract_for(*, pair_id: str, scenario_id: str, family: str, role: str, generator_family: str, generator_parameters: dict, seed: int, base_input_hash: str) -> ExecutionAttemptContract:
    clean = role == "clean"
    spec = {
        "V01": ("ruflex.application.training.train_model", "train_model", "training_run", "PREVENTED_STRUCTURALLY"),
        "V06": ("ruflex.application.training.select_validation_threshold", "select_validation_threshold", "decision_threshold", "PREVENTED_BY_FIREWALL"),
        "V07": ("ruflex.application.training.fit_validation_calibration", "fit_validation_calibration", "calibration_transform", "PREVENTED_BY_FIREWALL"),
    }
    entrypoint, operation, artifact, corrupt_outcome = spec[family]
    return ExecutionAttemptContract(
        study_revision="study02-preunlock-native-v2",
        pair_id=pair_id,
        scenario_id=scenario_id,
        violation_family=family,
        clean_or_corrupt=role,
        product_sha=PRODUCT_SHA256,
        expected_product_entrypoint=entrypoint,
        operation_role=operation,
        data_roles=("train", "validation", "final_test"),
        allowed_source_roles=("train",) if family == "V01" else ("validation",),
        forbidden_source_roles=("final_test",),
        artifact_type_expected=artifact,
        expected_semantic_outcome="ALLOWED_VALID" if clean else corrupt_outcome,
        persistence_required=True,
        oracle_reference_id=f"{pair_id}:{role}",
        generator_family=generator_family,
        generator_parameters=generator_parameters,
        seed=seed,
        base_input_hash=base_input_hash,
    )


RAW_RESULT_FIELDS = (
    "study_revision", "product_sha", "protocol_sha", "manifest_id", "execution_plan_hash",
    "pair_id", "scenario_id", "family", "seed", "clean_or_corrupt", "product_entrypoint",
    "requested_data_role", "resolved_data_role", "product_outcome", "product_exception_type",
    "product_exception_message_normalized", "artifact_created", "artifact_type", "artifact_id",
    "artifact_provenance_hash", "false_block", "false_warning", "baseline_outcome",
    "baseline_alert_count", "persistence_required", "save_status", "reopen_status",
    "reopened_artifact_provenance_hash", "runtime_ms", "generator_family", "generator_parameters",
    "execution_contract_hash", "base_input_hash", "clean_input_hash", "corrupt_input_hash",
    "action_attempted", "invalid_artifact_persisted", "failure_class",
)
