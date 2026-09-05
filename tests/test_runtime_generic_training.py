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
    assurance = create_assurance_case(root)
    exported = export_verification_bundle(root)
    assert final.run_id == run.run_id
    assert assurance.assurance_id
    assert validate_verification_bundle(Path(exported["path"])).status == "PASS"


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


@pytest.mark.parametrize("adapter_key,model_kind,parameters", [
    ("ruflex_flat_neuro_fuzzy", "flat_neuro_fuzzy", {"max_epochs": 2, "batch_size": 16, "patience": 2, "max_rules": 3, "learning_rate": .01}),
    ("sklearn_linear", "logistic_regression", {}),
    ("sklearn_decision_tree", "decision_tree", {"max_depth": 2}),
    ("sklearn_random_forest", "random_forest", {"n_estimators": 3}),
    ("sklearn_gradient_boosting", "gradient_boosting", {"n_estimators": 3, "learning_rate": .1, "max_depth": 2}),
])
def test_generic_core_service_executes_builtin_sklearn_adapters(tmp_path: Path, adapter_key: str, model_kind: str, parameters: dict) -> None:
    _project(tmp_path)
    run = train_with_adapter(tmp_path, registry=builtin_runtime_registry(), adapter_key=adapter_key, model_kind=model_kind, seed=8, parameters=parameters)
    assert run.adapter_key == adapter_key
    assert run.model_artifact_sha256
    assert run.validation_metrics
    with ArtifactStore(tmp_path).open(ArtifactRef(sha256=run.model_artifact_sha256)) as handle:
        result = builtin_runtime_registry().resolve_model_adapter(adapter_key).predict(PredictionRequest(task="binary_classification", feature_names=("x",), features=np.asarray([[.2], [.8]]), artifact=handle.read(), model_spec=run.model_spec, preprocessing_identity=run.preprocessing_artifact_sha256 or ""))
    assert len(result.prediction) == 2
    assert result.probability is not None
