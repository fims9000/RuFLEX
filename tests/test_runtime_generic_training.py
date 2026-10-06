from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd
import pytest

from ruflex.application.datasets import build_dataset_contract, create_split_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.runtime_training import train_with_adapter
from ruflex.application.training import load_training_run
from ruflex.application.datasets import load_transform_pipeline_contract
from ruflex.application.artifacts import ArtifactRef, ArtifactStore
from ruflex.application.assurance import create_assurance_case
from ruflex.application.lineage import build_project_lineage
from ruflex.application.projects import ProjectService
from ruflex.application.selective import create_selective_policy
from ruflex.application.verification_bundle import export_verification_bundle, validate_verification_bundle
from ruflex.domain.evidence import ExplanationContract, FeatureAttribution
from ruflex.runtime.contracts import ExecutionBackendDescriptor, ExplainerDescriptor, ExplainerRequest, ExplainerResult, FitRequest, FitResult, ModelAdapterDescriptor, PredictionRequest, PredictionResult, RuntimeIdentity
from ruflex.runtime.registry import RuntimeRegistry
from ruflex.runtime import builtin_runtime_registry


@dataclass(frozen=True)
class FixtureAdapter:
    descriptor = ModelAdapterDescriptor(
        identity=RuntimeIdentity(key="fixture_adapter", version="1", provider="ruflex.tests", kind="model_adapter"),
        family="Fixture", training_model_kinds=("fixture_model",), supported_tasks=("binary_classification",),
        capabilities={"fit": True, "predict": True, "predict_proba": True},
    )

    def fit(self, request: FitRequest) -> FitResult:
        assert not hasattr(request, "X_test")
        raw = np.asarray(request.X_validation, dtype=float)[:, 0] - .5
        return FitResult(serialized_artifact=json.dumps({"fixture": True}).encode(), artifact_media_type="application/vnd.ruflex.fixture+json", model_spec={"fixture": True}, training_summary={"epochs_ran": 1}, validation_raw_predictions=raw.tolist(), validation_raw_probabilities=(1 / (1 + np.exp(-raw))).tolist())

    def predict(self, request: PredictionRequest) -> PredictionResult:
        raw = np.asarray(request.features, dtype=float)[:, 0] - .5
        return PredictionResult(prediction=(raw >= 0).astype(float).tolist(), raw_score=raw.tolist(), probability=(1 / (1 + np.exp(-raw))).tolist())


@dataclass(frozen=True)
class FixtureExplainer:
    descriptor = ExplainerDescriptor(
        identity=RuntimeIdentity(key="fixture_explainer", version="1", provider="ruflex.tests", kind="explainer"),
        supported_tasks=("binary_classification",),
    )

    def supports(self, *, run_capabilities: dict[str, str], task: str, artifact: str) -> tuple[bool, str | None]:
        return task == "binary_classification", None

    def explain(self, request: ExplainerRequest) -> ExplainerResult:
        from ruflex.application.training import load_training_run
        run = load_training_run(request.project_root, request.run_id)
        value = float(request.sample["x"])
        return ExplainerResult(explanation=ExplanationContract(
            run_id=run.run_id, model_kind=run.model_kind, model_artifact_sha256=run.model_artifact_sha256,
            sample={"x": value}, target=run.target, family="occlusion", method="train_reference_occlusion",
            prediction=value, reference_definition="fixture train-derived reference", explainer_key="fixture_explainer",
            explainer_version="1", explainer_provider="ruflex.tests",
            attributions=[FeatureAttribution(feature="x", observed_value=value, reference_value=0.0, attribution=value)],
        ))


def _project(root: Path) -> None:
    frame = pd.DataFrame({"x": range(40), "target": [index % 2 for index in range(40)]})
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)


def test_generic_core_service_persists_external_adapter_without_project_access(tmp_path: Path) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry()
    registry.register_model_adapter(FixtureAdapter())
    registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", seed=4)
    reopened = load_training_run(tmp_path, run.run_id)
    assert reopened.adapter_key == "fixture_adapter"
    assert reopened.model_kind == "fixture_model"
    assert reopened.preprocessing_artifact_sha256
    assert reopened.transform_pipeline_id
    pipeline = load_transform_pipeline_contract(tmp_path, reopened.transform_pipeline_id)
    assert pipeline.fit_role == "TRAIN"
    assert [step.step_type for step in pipeline.steps] == ["MedianImputer", "StandardScaler"]
    assert reopened.split.test_status == "LOCKED_NOT_EVALUATED"


def test_external_adapter_receives_a_persisted_group_split_without_test_access(tmp_path: Path) -> None:
    frame = pd.DataFrame({"patient_id": [f"p{index // 3}" for index in range(45)], "x": range(45), "target": [index % 2 for index in range(45)]})
    source = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["patient_id"])
    persist_dataset_contract(tmp_path, contract, run_data_audit(contract, frame), profile)
    split = create_split_contract(tmp_path, family="GROUP", group_column="patient_id", split_seed=13)
    registry = RuntimeRegistry(); registry.register_model_adapter(FixtureAdapter()); registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", split_seed=13, training_seed=31, split_contract_id=str(split.split_id))
    assert run.split.family == "group"
    assert run.split.split_contract_id == str(split.split_id)
    assert run.split.role_identity_hashes == split.role_identity_hashes
    assert run.split.test_count == len(split.role_source_rows["test"])


def test_train_only_ordinal_encoding_is_persisted_and_replayed_for_categorical_features(tmp_path: Path, monkeypatch) -> None:
    frame = pd.DataFrame({
        "x": list(range(60)),
        "material": ["steel", "alloy", "polymer"] * 20,
        "target": [index % 2 for index in range(60)],
    })
    source = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification")
    persist_dataset_contract(tmp_path, contract, run_data_audit(contract, frame), profile)
    registry = RuntimeRegistry(); registry.register_model_adapter(FixtureAdapter()); registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", seed=4)
    pipeline = load_transform_pipeline_contract(tmp_path, run.transform_pipeline_id)
    ordinal = next(step for step in pipeline.steps if step.step_type == "OrdinalEncoder")
    assert ordinal.input_columns == ["material"]
    assert set(ordinal.parameters["categories"]["material"]) == {"alloy", "polymer", "steel"}
    assert ordinal.parameters["unknown_value"] == -1.0
    monkeypatch.setattr("ruflex.application.training.builtin_runtime_registry", lambda: registry)
    from ruflex.application.training import create_validation_evaluation, evaluate_final_test, select_validation_threshold
    evaluation = create_validation_evaluation(tmp_path, run.run_id)
    threshold = select_validation_threshold(tmp_path, evaluation.evaluation_id)
    assert evaluate_final_test(tmp_path, evaluation.evaluation_id, threshold_id=threshold.threshold_id).prediction_rows


def test_external_adapter_replays_through_evidence_without_model_kind_branches(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry(); registry.register_model_adapter(FixtureAdapter()); registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", seed=4)
    monkeypatch.setattr("ruflex.application.evidence.builtin_runtime_registry", lambda: registry)
    from ruflex.application.evidence import predict_run_sample
    probability = predict_run_sample(tmp_path, run.run_id, {"x": 3.0})
    assert 0.0 <= probability <= 1.0


def test_train_model_uses_an_explicit_external_adapter_identity(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry(); registry.register_model_adapter(FixtureAdapter()); registry.freeze()
    monkeypatch.setattr("ruflex.runtime.registry.builtin_runtime_registry", lambda: registry)
    from ruflex.application.training import train_model

    run = train_model(tmp_path, model_kind="fixture_model", adapter_key="fixture_adapter", seed=4)
    assert (run.model_kind, run.adapter_key, run.adapter_provider) == ("fixture_model", "fixture_adapter", "ruflex.tests")


def test_external_adapter_replays_final_test_via_its_persisted_runtime_identity(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry(); registry.register_model_adapter(FixtureAdapter()); registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", seed=4)
    from ruflex.application.training import create_validation_evaluation, evaluate_final_test, select_validation_threshold
    monkeypatch.setattr("ruflex.application.training.builtin_runtime_registry", lambda: registry)
    evaluation = create_validation_evaluation(tmp_path, run.run_id)
    threshold = select_validation_threshold(tmp_path, evaluation.evaluation_id)
    final = evaluate_final_test(tmp_path, evaluation.evaluation_id, threshold_id=threshold.threshold_id)
    assert final.run_id == run.run_id
    assert final.prediction_rows


def test_external_explainer_is_persisted_by_the_generic_core_route(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry(); registry.register_model_adapter(FixtureAdapter()); registry.register_component(FixtureExplainer.descriptor, implementation=FixtureExplainer()); registry.freeze()
    run = train_with_adapter(tmp_path, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model", seed=4)
    monkeypatch.setattr("ruflex.runtime.builtin_runtime_registry", lambda: registry)
    monkeypatch.setattr("ruflex.application.capabilities.builtin_runtime_registry", lambda: registry)
    from ruflex.application.evidence import create_runtime_explanation, load_explanation

    explanation = create_runtime_explanation(tmp_path, explainer_key="fixture_explainer", run_id=run.run_id, sample={"x": 3.0})
    assert explanation.explainer_key == "fixture_explainer"
    assert load_explanation(tmp_path, explanation.explanation_id) == explanation


def test_external_runtime_governed_golden_route_reopens_and_exports_portable_evidence(tmp_path: Path, monkeypatch) -> None:
    """Exercise the generic lifecycle with an external adapter, not a built-in branch."""
    root = tmp_path / "external-governed-route"
    ProjectService().create(root, name="External governed route")
    frame = pd.DataFrame({
        "patient_id": [f"p{index // 3}" for index in range(45)],
        "x": range(45),
        "target": [index % 2 for index in range(45)],
    })
    source = persist_dataset_bytes(root, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["patient_id"])
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    split = create_split_contract(root, family="GROUP", group_column="patient_id", split_seed=13)
    registry = RuntimeRegistry()
    registry.register_model_adapter(FixtureAdapter())
    registry.register_component(FixtureExplainer.descriptor, implementation=FixtureExplainer())
    registry.freeze()
    run = train_with_adapter(
        root, registry=registry, adapter_key="fixture_adapter", model_kind="fixture_model",
        split_seed=13, training_seed=31, split_contract_id=str(split.split_id),
    )
    monkeypatch.setattr("ruflex.application.training.builtin_runtime_registry", lambda: registry)
    monkeypatch.setattr("ruflex.application.evidence.builtin_runtime_registry", lambda: registry)
    monkeypatch.setattr("ruflex.runtime.builtin_runtime_registry", lambda: registry)
    monkeypatch.setattr("ruflex.application.capabilities.builtin_runtime_registry", lambda: registry)
    from ruflex.application.evidence import create_runtime_explanation, load_explanation
    from ruflex.application.training import TrainingError, create_validation_evaluation, evaluate_final_test, select_validation_threshold

    evaluation = create_validation_evaluation(root, run.run_id)
    threshold = select_validation_threshold(root, evaluation.evaluation_id)
    policy = create_selective_policy(root, evaluation.evaluation_id, confidence_cutoff=.6, threshold_id=threshold.threshold_id)
    explanation = create_runtime_explanation(root, explainer_key="fixture_explainer", run_id=run.run_id, sample={"x": 3.0})
    final = evaluate_final_test(root, evaluation.evaluation_id, threshold_id=threshold.threshold_id, selective_policy_id=policy.policy_id)
    with pytest.raises(TrainingError, match="cannot be tuned after final-test access"):
        create_selective_policy(root, evaluation.evaluation_id, confidence_cutoff=.7, threshold_id=threshold.threshold_id)

    reopened = ProjectService().open(root, read_only=True)
    assert reopened.read_only
    assert load_training_run(root, run.run_id).split.split_contract_id == str(split.split_id)
    assert load_explanation(root, explanation.explanation_id).explainer_key == "fixture_explainer"
    lineage = build_project_lineage(root)
    assert {"dataset", "training_run", "evaluation", "decision_threshold", "selective_policy", "explanation", "final_test_evaluation"} <= {node.kind for node in lineage.nodes}
    run_node = next(node for node in lineage.nodes if node.kind == "training_run" and node.object_id == str(run.run_id))
    assert "fixture_adapter@1" in run_node.detail
    assert run.model_artifact_sha256[:12] in run_node.detail
    assert run.preprocessing_artifact_sha256[:12] in run_node.detail
    assurance = create_assurance_case(root)
    exported = export_verification_bundle(root)
    assert final.run_id == run.run_id
    assert assurance.assurance_id
    assert validate_verification_bundle(Path(exported["path"])).status == "PASS"
    # Final-test and Evidence must share the same adapter-backed probability
    # semantics for an identical raw case, not merely return plausible values.
    from ruflex.application.datasets import load_dataset_frame
    from ruflex.application.evidence import predict_run_sample

    first_test = final.prediction_rows[0]
    raw_case = load_dataset_frame(root).iloc[int(first_test.source_row)]
    sample = {feature: float(raw_case[feature]) for feature in run.feature_columns}
    evidence_probability = predict_run_sample(root, run.run_id, sample)
    assert evidence_probability == pytest.approx(first_test.probability, abs=1e-12)


def test_study_job_resume_keeps_exact_external_model_adapter(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path)
    registry = RuntimeRegistry()
    registry.register_model_adapter(FixtureAdapter())
    registry.freeze()
    monkeypatch.setattr("ruflex.application.training.builtin_runtime_registry", lambda: registry)
    monkeypatch.setattr("ruflex.runtime.registry.builtin_runtime_registry", lambda: registry)

    backend_descriptor = ExecutionBackendDescriptor(
        identity=RuntimeIdentity(key="fixture_sync_backend", version="1", provider="ruflex.tests", kind="execution_backend"),
        supports_cancel=True,
        supports_resume=True,
    )

    class SynchronousBackend:
        def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            operation()
            return True

        def resume(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            operation()
            return True

        def is_active(self, *, project_root: Path, job_id: UUID) -> bool:
            return False

        def cancel(self, *, project_root: Path, job_id: UUID) -> bool:
            return True

    backend = SynchronousBackend()
    monkeypatch.setattr(
        "ruflex.application.training.resolve_execution_backend",
        lambda key: (backend_descriptor, backend),
    )

    from ruflex.application.training import load_training_study, start_study_job

    job = start_study_job(
        tmp_path,
        name="External adapter recovery",
        model_kind="fixture_model",
        adapter_key="fixture_adapter",
        adapter_version="1",
        execution_backend_key="fixture_sync_backend",
        seeds=[1, 2, 3],
        selection_metric="f1",
    )

    assert job.status == "SUCCEEDED"
    assert (job.adapter_key, job.adapter_version, job.adapter_provider) == (
        "fixture_adapter", "1", "ruflex.tests"
    )
    study = load_training_study(tmp_path, job.study_id)
    assert (study.adapter_key, study.adapter_version, study.adapter_provider) == (
        "fixture_adapter", "1", "ruflex.tests"
    )
    assert {(run.adapter_key, run.adapter_version) for run in study.seed_runs} == {("fixture_adapter", "1")}


def test_study_job_persists_and_uses_the_selected_external_execution_backend(tmp_path: Path, monkeypatch) -> None:
    """A backend choice is immutable job provenance, not a local-executor alias."""
    _project(tmp_path)
    descriptor = ExecutionBackendDescriptor(
        identity=RuntimeIdentity(key="fixture_execution_backend", version="1", provider="ruflex.tests", kind="execution_backend"),
        supports_cancel=True,
        supports_resume=True,
    )

    class SynchronousBackend:
        submissions: list[UUID] = []

        def submit(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            self.submissions.append(job_id)
            operation()
            return True

        def is_active(self, *, project_root: Path, job_id: UUID) -> bool:
            return False

        def status(self, *, project_root: Path, job_id: UUID) -> str:
            return "IDLE"

        def cancel(self, *, project_root: Path, job_id: UUID) -> bool:
            return True

        def resume(self, *, project_root: Path, job_id: UUID, operation: Callable[[], None]) -> bool:
            return self.submit(project_root=project_root, job_id=job_id, operation=operation)

    backend = SynchronousBackend()
    monkeypatch.setattr(
        "ruflex.application.training.resolve_execution_backend",
        lambda key="local_executor": (descriptor, backend) if key == descriptor.identity.key else (_ for _ in ()).throw(AssertionError(key)),
    )
    from ruflex.application.training import load_study_job, start_study_job

    job = start_study_job(
        tmp_path, name="external backend study", model_kind="logistic_regression", seeds=[3, 5, 7],
        selection_metric="f1", execution_backend_key=descriptor.identity.key, max_epochs=1,
    )
    persisted = load_study_job(tmp_path, job.job_id)
    assert backend.submissions == [job.job_id]
    assert persisted.status == "SUCCEEDED"
    assert (persisted.execution_backend_key, persisted.execution_backend_version, persisted.execution_backend_provider) == (
        descriptor.identity.key, descriptor.identity.version, descriptor.identity.provider,
    )


def test_study_job_request_id_recovers_existing_job_and_rejects_config_mismatch(tmp_path: Path, monkeypatch) -> None:
    from uuid import uuid4

    _project(tmp_path)
    from ruflex.application import training as training_app

    monkeypatch.setattr(training_app, "_submit_study_job", lambda root, job_id: training_app.load_study_job(root, job_id))
    request_id = uuid4()
    request = {
        "client_request_id": request_id,
        "name": "recoverable study",
        "model_kind": "logistic_regression",
        "seeds": [3, 5, 7],
        "selection_metric": "f1",
        "execution_backend_key": "local_executor",
        "max_epochs": 2,
    }

    first = training_app.start_study_job(tmp_path, **request)
    retry = training_app.start_study_job(tmp_path, **request)

    assert first.job_id == retry.job_id == request_id
    assert retry.client_request_id == request_id
    assert len(list((tmp_path / "studies" / "jobs").glob("*.json"))) == 1
    with pytest.raises(training_app.TrainingError, match="different frozen configuration"):
        training_app.start_study_job(tmp_path, **{**request, "max_epochs": 3})


def test_cancel_requested_during_last_seed_is_not_overwritten_by_success_finalization(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path)
    from ruflex.application import training as training_app

    original_train_model = training_app.train_model
    seed_values = [3, 5, 7]

    def cancel_after_last_fit(*args, **kwargs):
        run = original_train_model(*args, **kwargs)
        if kwargs.get("training_seed") == seed_values[-1]:
            job = training_app.list_study_jobs(tmp_path)[-1]
            training_app.cancel_study_job(tmp_path, job.job_id)
        return run

    def execute_synchronously(root: Path, job_id: UUID):
        training_app._execute_study_job(root, job_id)
        return training_app.load_study_job(root, job_id)

    monkeypatch.setattr(training_app, "train_model", cancel_after_last_fit)
    monkeypatch.setattr(training_app, "_submit_study_job", execute_synchronously)
    job = training_app.start_study_job(
        tmp_path,
        name="cancel at final fit",
        model_kind="logistic_regression",
        seeds=seed_values,
        selection_metric="f1",
        randomness_protocol="TRAINING_VARIABILITY",
        split_seed=42,
        max_epochs=1,
        validation_fraction=.2,
        test_fraction=.2,
    )

    assert job.cancel_requested is True
    assert job.status == "CANCELLED"
    assert [state.status for state in job.seed_states] == ["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"]
    assert job.study_id is None
    assert not (tmp_path / "studies" / "active-study.json").exists()


@pytest.mark.parametrize("adapter_key,model_kind,parameters", [
    ("native_flat_neuro_fuzzy", "flat_neuro_fuzzy", {"max_epochs": 2, "batch_size": 16, "patience": 2, "max_rules": 3, "learning_rate": .01}),
    ("native_linear", "logistic_regression", {}),
    ("native_decision_tree", "decision_tree", {"max_depth": 2}),
    ("native_random_forest", "random_forest", {"n_estimators": 3}),
    ("native_gradient_boosting", "gradient_boosting", {"n_estimators": 3, "learning_rate": .1, "max_depth": 2}),
])
def test_generic_core_service_executes_builtin_native_adapters(tmp_path: Path, adapter_key: str, model_kind: str, parameters: dict) -> None:
    _project(tmp_path)
    run = train_with_adapter(tmp_path, registry=builtin_runtime_registry(), adapter_key=adapter_key, model_kind=model_kind, seed=8, parameters=parameters)
    assert run.adapter_key == adapter_key
    assert run.model_artifact_sha256
    assert run.validation_metrics
    with ArtifactStore(tmp_path).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        result = builtin_runtime_registry().resolve_model_adapter(adapter_key).predict(PredictionRequest(task="binary_classification", feature_names=("x",), features=np.asarray([[.2], [.8]]), artifact=handle.read(), model_spec=run.model_spec, preprocessing_identity=run.preprocessing_artifact_sha256 or ""))
    assert len(result.prediction) == 2
    assert result.probability is not None
    assert result.raw_score is not None
    assert np.allclose(result.probability, 1.0 / (1.0 + np.exp(-np.asarray(result.raw_score))), rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize(("model_kind", "parameters"), [
    ("flat_neuro_fuzzy", {"max_epochs": 2, "batch_size": 16, "patience": 2, "max_rules": 3, "learning_rate": .01}),
    ("logistic_regression", {}),
    ("linear_regression", {}),
    ("decision_tree", {"max_depth": 3}),
    ("random_forest", {"n_estimators": 4, "max_depth": 3}),
    ("gradient_boosting", {"n_estimators": 4, "learning_rate": .1, "max_depth": 2}),
])
def test_native_adapter_fit_and_replay_preserve_pre_dispatch_numeric_semantics(
    tmp_path: Path, model_kind: str, parameters: dict,
) -> None:
    """Compare adapter dispatch with the retained pre-dispatch fit implementations."""
    from ruflex.application.evidence import predict_run_sample
    from ruflex.application.training import (
        create_validation_evaluation,
        evaluate_final_test,
        select_validation_threshold,
        train_decision_tree,
        train_flat_neuro_fuzzy,
        train_gradient_boosting,
        train_linear_baseline,
        train_model,
        train_random_forest,
    )

    task = "regression" if model_kind == "linear_regression" else "binary_classification"
    frame = pd.DataFrame({
        "x": np.arange(60, dtype=float),
        "target": (0.25 * np.arange(60) + np.sin(np.arange(60) / 5.0)) if task == "regression" else (np.arange(60) >= 30).astype(int),
    })
    source = persist_dataset_bytes(tmp_path, frame.to_csv(index=False).encode())
    profile = inspect_dataset(frame, source_artifact_sha256=source.sha256)
    contract = build_dataset_contract(profile, target="target", task=task)
    persist_dataset_contract(tmp_path, contract, run_data_audit(contract, frame), profile)

    seed_args = {"split_seed": 17, "training_seed": 23, "seed": 23}
    if model_kind == "flat_neuro_fuzzy":
        before = train_flat_neuro_fuzzy(tmp_path, **seed_args, **parameters)
    elif model_kind in {"logistic_regression", "linear_regression"}:
        before = train_linear_baseline(tmp_path, kind=model_kind, **seed_args)
    elif model_kind == "decision_tree":
        before = train_decision_tree(tmp_path, **seed_args, **parameters)
    elif model_kind == "random_forest":
        before = train_random_forest(tmp_path, **seed_args, **parameters)
    else:
        before = train_gradient_boosting(tmp_path, **seed_args, **parameters)
    after = train_model(tmp_path, model_kind=model_kind, **seed_args, **parameters)

    assert before.feature_columns == after.feature_columns
    assert before.split.split_identity == after.split.split_identity
    numerical_tolerance = 1e-5 if model_kind == "flat_neuro_fuzzy" else 1e-12
    # The canonical generic path adds secondary calibration/ROC metrics that
    # older model-specific TrainingRun summaries did not always persist.
    shared_metrics = before.validation_metrics.keys() & after.validation_metrics.keys()
    assert shared_metrics
    for metric in shared_metrics:
        assert after.validation_metrics[metric] == pytest.approx(before.validation_metrics[metric], abs=numerical_tolerance)
    assert len(before.prediction_preview) == len(after.prediction_preview)
    for old_row, new_row in zip(before.prediction_preview, after.prediction_preview, strict=True):
        assert new_row.source_row == old_row.source_row
        assert new_row.target == pytest.approx(old_row.target, abs=1e-12)
        assert new_row.prediction == pytest.approx(old_row.prediction, abs=numerical_tolerance)
        assert new_row.probability == pytest.approx(old_row.probability, abs=numerical_tolerance)
        assert new_row.predicted_label == old_row.predicted_label

    old_evaluation = create_validation_evaluation(tmp_path, before.run_id)
    new_evaluation = create_validation_evaluation(tmp_path, after.run_id)
    old_threshold = select_validation_threshold(tmp_path, old_evaluation.evaluation_id) if task == "binary_classification" else None
    new_threshold = select_validation_threshold(tmp_path, new_evaluation.evaluation_id) if task == "binary_classification" else None
    old_final = evaluate_final_test(tmp_path, old_evaluation.evaluation_id, threshold_id=None if old_threshold is None else old_threshold.threshold_id)
    new_final = evaluate_final_test(tmp_path, new_evaluation.evaluation_id, threshold_id=None if new_threshold is None else new_threshold.threshold_id)
    assert len(old_final.prediction_rows) == len(new_final.prediction_rows)
    for old_row, new_row in zip(old_final.prediction_rows, new_final.prediction_rows, strict=True):
        assert new_row.source_row == old_row.source_row
        assert new_row.target == pytest.approx(old_row.target, abs=1e-12)
        assert new_row.prediction == pytest.approx(old_row.prediction, abs=numerical_tolerance)
        assert new_row.probability == pytest.approx(old_row.probability, abs=numerical_tolerance)
        assert new_row.predicted_label == old_row.predicted_label

    sample = {"x": float(frame.loc[old_final.prediction_rows[0].source_row, "x"])}
    assert predict_run_sample(tmp_path, after.run_id, sample) == pytest.approx(
        predict_run_sample(tmp_path, before.run_id, sample), abs=numerical_tolerance,
    )
