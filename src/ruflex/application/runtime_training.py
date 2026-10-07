"""Core-owned generic training service for typed model adapters.

Adapters receive only prepared TRAIN/VALIDATION arrays.  This module owns the
DatasetContract, preprocessing artifact, canonical validation evidence and all
persistence; neither built-ins nor entry-point adapters receive a project root.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ruflex.application.artifacts import ArtifactMetadata, ArtifactStore
from ruflex.application.datasets import create_transform_pipeline_contract, load_dataset_contract, load_dataset_frame, load_split_contract, run_leakage_audit
from ruflex.application.training import (
    _baseline_metrics, _normalization_dict, _persist_preprocessing_artifact,
    _ensure_validation_policy_selection_open, _provenance, _resolve_randomness, _split_identity, _validation_payload,
    persist_training_run,
)
from ruflex.core.enums import NormalizationMode
from ruflex.data.datasets import DatasetConfig, TabularDataset
from ruflex.domain.training import EpochPoint, TrainingRun
from ruflex.runtime.contracts import FitRequest
from ruflex.runtime.errors import RuntimeIncompatibleError
from ruflex.runtime.registry import RuntimeRegistry


def train_with_adapter(
    project_root: Path, *, registry: RuntimeRegistry, adapter_key: str, adapter_version: str | None = None,
    model_kind: str, seed: int | None = None, split_seed: int | None = None,
    training_seed: int | None = None, validation_fraction: float = .2,
    test_fraction: float = .2, parameters: dict | None = None,
    split_contract_id: str | None = None, declared_training_config: dict | None = None,
) -> TrainingRun:
    """Execute one trusted adapter while retaining the core data firewall."""
    _ensure_validation_policy_selection_open(project_root)
    adapter = registry.resolve_model_adapter(adapter_key, version=adapter_version)
    if model_kind not in adapter.descriptor.training_model_kinds:
        raise RuntimeIncompatibleError(f"Adapter {adapter_key!r} cannot train model kind {model_kind!r}.")
    contract = load_dataset_contract(project_root)
    if contract.task not in adapter.descriptor.supported_tasks:
        raise RuntimeIncompatibleError(f"Adapter {adapter_key!r} does not support task {contract.task!r}.")
    resolved_split, resolved_training, protocol = _resolve_randomness(seed=seed, split_seed=split_seed, training_seed=training_seed)
    frame = load_dataset_frame(project_root)
    split_contract = load_split_contract(project_root, split_contract_id) if split_contract_id else None
    if split_contract is not None:
        if split_contract.split_seed != resolved_split:
            raise RuntimeIncompatibleError("The requested split_seed does not match the immutable SplitContract.")
        if split_contract.validation_fraction != validation_fraction or split_contract.test_fraction != test_fraction:
            raise RuntimeIncompatibleError("Training fractions must match the immutable SplitContract.")
    try:
        normalization_mode = NormalizationMode((parameters or {}).get("normalization", NormalizationMode.STANDARD.value))
    except ValueError as error:
        raise RuntimeIncompatibleError("Unsupported normalization mode; use none, standard, or minmax.") from error
    split = TabularDataset.from_dataframe(frame).split(DatasetConfig(
        target_column=contract.target, feature_columns=tuple(contract.feature_columns),
        validation_fraction=validation_fraction, test_fraction=test_fraction,
        normalization=normalization_mode, fill_missing="median", random_state=resolved_split,
        explicit_split_source_rows=(None if split_contract is None else split_contract.role_source_rows),
    ))
    if split.validation_features.shape[0] == 0:
        raise RuntimeIncompatibleError("The resolved validation split is empty.")
    preprocessing_sha = _persist_preprocessing_artifact(project_root, contract, split)
    transform_pipeline = create_transform_pipeline_contract(project_root, contract=contract, split=split, preprocessing_artifact_sha256=preprocessing_sha, split_contract_id=(None if split_contract is None else str(split_contract.split_id)))
    leakage_audit = run_leakage_audit(project_root, split_contract_id=(None if split_contract is None else str(split_contract.split_id)), transform_pipeline_id=str(transform_pipeline.pipeline_id), rigor_profile=str((parameters or {}).get("rigor_profile", "CONFIRMATORY")).upper())
    if leakage_audit.status == "FAIL":
        raise RuntimeIncompatibleError("Data-leakage audit failed; training is blocked until declared provenance is corrected.")
    request = FitRequest(
        task=contract.task, feature_names=tuple(contract.feature_columns),
        X_train=np.asarray(split.train_features), y_train=np.asarray(split.train_targets),
        X_validation=np.asarray(split.validation_features), y_validation=np.asarray(split.validation_targets),
        split_identity=(_split_identity(contract.dataset_fingerprint, split) if split_contract is None else split_contract.split_identity), split_seed=resolved_split,
        training_seed=resolved_training, validated_parameters=dict(parameters or {}),
        preprocessing_identity=preprocessing_sha,
    )
    result = adapter.fit(request)
    # Core owns dataset/preprocessing provenance even when an adapter chooses
    # a declarative JSON artifact representation.  This does not alter model
    # parameters or predictions; it binds the result to the canonical input.
    serialized_artifact = result.serialized_artifact
    if result.artifact_media_type.endswith("+json"):
        payload = json.loads(serialized_artifact.decode("utf-8"))
        payload.setdefault("target", contract.target)
        payload.setdefault("normalization", _normalization_dict(split.normalization))
        payload.setdefault("split_seed", resolved_split)
        payload.setdefault("training_seed", resolved_training)
        serialized_artifact = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    artifact = ArtifactStore(project_root).ingest_bytes(
        serialized_artifact,
        metadata=ArtifactMetadata(
            media_type=result.artifact_media_type, source_kind="generated",
            original_name=f"{model_kind}.runtime-artifact", parent_artifacts=[contract.source_artifact_sha256, preprocessing_sha],
            producer={"component": "ruflex.runtime", "adapter": adapter.descriptor.identity.canonical_key},
        ),
    )
    raw = np.asarray(result.validation_raw_predictions, dtype=float).reshape(-1)
    preview, confusion, calibration = _validation_payload(contract.task, split.validation_targets, raw, source_rows=split.validation_indices, dataset_fingerprint=contract.dataset_fingerprint)
    metrics = _baseline_metrics(contract.task, split.validation_targets, raw)
    loss = metrics["mse"] if contract.task == "regression" else 1.0 - metrics["accuracy"]
    training_summary = {
        "source": adapter.descriptor.identity.key,
        "epochs_ran": 1,
        "best_epoch": 1,
        "monitor_name": "validation_loss",
        "best_monitor_value": loss,
        "train_loss": loss,
        "train_metrics": {},
        "validation_loss": loss,
        "history": [],
        **result.training_summary,
        "validation_metrics": metrics,
    }
    trajectory = [EpochPoint.model_validate(item) for item in result.trajectory] or [
        EpochPoint(epoch=0, train_loss=loss, validation_loss=loss, validation_metrics=metrics),
        EpochPoint(epoch=1, train_loss=loss, validation_loss=loss, validation_metrics=metrics),
    ]
    identity = adapter.descriptor.identity
    run = TrainingRun(
        schema_version=3, model_kind=model_kind, task=contract.task, target=contract.target,
        dataset_fingerprint=contract.dataset_fingerprint, dataset_artifact_sha256=contract.source_artifact_sha256,
        feature_columns=list(contract.feature_columns), seed=resolved_training, split_seed=resolved_split,
        training_seed=resolved_training, randomness_protocol=protocol,
        max_epochs=int(training_summary.get("epochs_ran", 1)), learning_rate=float((parameters or {}).get("learning_rate", 0.0)),
        batch_size=int((parameters or {}).get("batch_size", len(split.train_features))), patience=(parameters or {}).get("patience"),
        split=_provenance(contract, split, split_seed=resolved_split, validation_fraction=validation_fraction, test_fraction=test_fraction, split_contract=split_contract),
        model_spec={"model_kind": model_kind, **result.model_spec}, normalization=_normalization_dict(split.normalization),
        preprocessing_artifact_sha256=preprocessing_sha, transform_pipeline_id=str(transform_pipeline.pipeline_id), leakage_audit_id=str(leakage_audit.audit_id), training_summary=training_summary, trajectory=trajectory,
        validation_metrics=metrics, prediction_preview=preview, confusion_matrix=confusion, calibration=calibration,
        model_artifact_sha256=artifact.sha256, adapter_key=identity.key, adapter_version=identity.version,
        adapter_provider=identity.provider, adapter_kind=identity.kind, runtime_capability_snapshot_hash=registry.snapshot()["sha256"],
        declared_training_config=declared_training_config,
    )
    persist_training_run(project_root, run, registry=registry)
    return run
