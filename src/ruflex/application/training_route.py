"""Compatibility facade for the original RuFLEX real-training vertical slice.

The current product uses :mod:`ruflex.application.training` directly.  This
module preserves the earlier public application import used by old project
clients/tests while delegating every computation to the canonical training and
analysis services.  It is intentionally a thin adapter, not a second training
implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from ruflex.application.artifacts import ArtifactMetadata, ArtifactStore
from ruflex.application.training import (
    create_validation_evaluation,
    load_latest_training_run,
    train_flat_neuro_fuzzy,
)
from ruflex.domain.training import TrainingRun


def _compat_path(project_root: Path) -> Path:
    path = Path(project_root).resolve() / "runs" / "legacy-training-route.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _evaluation_artifact(project_root: Path, run: TrainingRun) -> str:
    evaluation = create_validation_evaluation(project_root, run.run_id)
    ref = ArtifactStore(project_root).ingest_bytes(
        evaluation.model_dump_json(indent=2).encode("utf-8"),
        metadata=ArtifactMetadata(
            media_type="application/vnd.ruflex.validation-evaluation+json",
            source_kind="generated",
            original_name=f"validation-{evaluation.evaluation_id}.json",
            parent_artifacts=[run.model_artifact_sha256],
            producer={"component": "ruflex.application.training_route.compat", "version": "1"},
        ),
    )
    _compat_path(project_root).write_text(
        json.dumps({"run_id": str(run.run_id), "evaluation_artifact_sha256": ref.sha256}, indent=2),
        encoding="utf-8",
    )
    return ref.sha256


def _view(run: TrainingRun, evaluation_artifact_sha256: str):
    return SimpleNamespace(
        run_id=run.run_id,
        trajectory=run.trajectory,
        best_epoch=int(run.training_summary.get("best_epoch", 0)),
        model_artifact_sha256=run.model_artifact_sha256,
        evaluation_artifact_sha256=evaluation_artifact_sha256,
        validation=SimpleNamespace(metrics=dict(run.validation_metrics), predictions=list(run.prediction_preview)),
    )


def train_configured_fis(
    project_root: Path,
    *,
    max_epochs: int = 20,
    patience: int | None = 8,
    learning_rate: float = 0.01,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    seed: int = 42,
    batch_size: int = 32,
    max_rules: int = 8,
):
    run = train_flat_neuro_fuzzy(
        project_root,
        seed=seed,
        max_epochs=max_epochs,
        learning_rate=learning_rate,
        batch_size=batch_size,
        patience=patience,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        max_rules=max_rules,
    )
    return _view(run, _evaluation_artifact(project_root, run))


def load_training_run(project_root: Path):
    run = load_latest_training_run(project_root)
    path = _compat_path(project_root)
    artifact_sha: str | None = None
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if UUID(payload["run_id"]) == run.run_id:
            artifact_sha = str(payload["evaluation_artifact_sha256"])
    if artifact_sha is None:
        artifact_sha = _evaluation_artifact(project_root, run)
    return _view(run, artifact_sha)
