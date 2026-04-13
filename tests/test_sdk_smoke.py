import numpy as np
import pandas as pd

from ruflex.core.enums import TaskType
from ruflex.sdk.project import Project
from ruflex.training.config import FineTuningOptions, ModelTrainingConfig, RefinementOptions, StagewiseOptions


def test_project_flat_smoke_roundtrip(tmp_path):
    rng = np.random.default_rng(42)
    x1 = rng.uniform(0.0, 1.0, size=64)
    x2 = rng.uniform(0.0, 1.0, size=64)
    y = 0.7 * x1 + 0.2 * x2
    frame = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

    project = Project(name="smoke", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.infer_variables(term_count=3)
    project.configure_flat_model(max_rules=4)

    summary = project.train(
        ModelTrainingConfig(
            task_type=TaskType.REGRESSION,
            use_stagewise_pretraining=False,
            use_bootstrap_initialization=True,
            stagewise=StagewiseOptions(epochs_per_stage=1, decision_epochs=1, refinement_rounds=1),
            fine_tuning=FineTuningOptions(max_epochs=2, batch_size=16, patience=1),
            refinement=RefinementOptions(cycles=1),
        )
    )

    assert summary.epochs_ran >= 1
    assert project.test_metrics is not None

    preds = project.predict(frame[["x1", "x2"]].head(5))
    assert preds.shape == (5, 1)

    text = project.explain(frame[["x1", "x2"]].head(2), as_text=True)
    assert "SAMPLE 0" in text

    dashboard = project.dashboard(frame[["x1", "x2"]].head(1))
    assert len(dashboard) == 1
    assert dashboard[0].decision_block.layer_kind == "decision"

    report = project.model_report()
    assert "MODEL REPORT" in report

    concept_flow_text = project.concept_flow(frame[["x1", "x2"]].head(1), as_text=True)
    assert "SAMPLE 0" in concept_flow_text

    bundle_path = tmp_path / "bundle"
    project.save(bundle_path)

    loaded = Project.load(bundle_path)
    loaded_preds = loaded.predict(frame[["x1", "x2"]].head(5))
    assert loaded_preds.shape == (5, 1)


def test_manual_rule_base_manifest_roundtrip(tmp_path):
    rng = np.random.default_rng(7)
    x1 = rng.uniform(0.0, 1.0, size=24)
    x2 = rng.uniform(0.0, 1.0, size=24)
    y = 0.4 * x1 + 0.4 * x2
    frame = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

    project = Project(name="manual-rules", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.infer_variables(term_count=3)
    project.configure_flat_model(max_rules=4)

    hidden_rule_base = project.make_rule_template(
        block_name=project.model_spec.feature_block.name,
        stage_name=project.model_spec.stage_name,
        layer_kind="hidden",
    )
    decision_rule_base = project.make_rule_template(
        block_name=project.model_spec.decision_layer.name,
        layer_kind="decision",
    )
    project.set_block_rule_base(
        project.model_spec.feature_block.name,
        hidden_rule_base,
        stage_name=project.model_spec.stage_name,
    )
    project.set_decision_rule_base(decision_rule_base)

    manifest_path = tmp_path / "project.json"
    project.save_manifest_json(manifest_path)

    loaded = Project.load_manifest_json(manifest_path, frame=frame)
    assert loaded.get_block_rule_base(
        loaded.model_spec.feature_block.name,
        stage_name=loaded.model_spec.stage_name,
    ) is not None
    assert loaded.get_decision_rule_base() is not None
    assert loaded.summary()["manual_rule_targets"] == 2


def test_project_deep_hybrid_residual_roundtrip_and_training(tmp_path):
    rng = np.random.default_rng(19)
    x1 = rng.uniform(0.0, 1.0, size=72)
    x2 = rng.uniform(0.0, 1.0, size=72)
    x3 = rng.uniform(0.0, 1.0, size=72)
    y = 0.5 * x1 + 0.3 * x2 * x3 + 0.1 * x3
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "y": y})

    project = Project(name="deep-hybrid", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.apply_workspace_template("deep_hybrid_residual")

    spec = project.model_spec
    assert spec is not None
    assert spec.decision_input_mode == "all_stages"
    assert len(spec.stages) >= 1
    assert len(spec.stages[0].blocks) >= 2
    assert spec.stages[0].blocks[0].input_indices != spec.stages[0].blocks[1].input_indices
    assert len(spec.decision_layer.variables) > spec.stages[-1].blocks[0].n_concepts

    manifest_path = tmp_path / "deep_hybrid_manifest.json"
    project.save_manifest_json(manifest_path)
    loaded = Project.load_manifest_json(manifest_path, frame=frame)
    assert loaded.model_spec is not None
    assert loaded.model_spec.decision_input_mode == "all_stages"

    summary = project.train(
        ModelTrainingConfig(
            task_type=TaskType.REGRESSION,
            use_stagewise_pretraining=True,
            use_bootstrap_initialization=True,
            stagewise=StagewiseOptions(epochs_per_stage=1, decision_epochs=1, refinement_rounds=1),
            fine_tuning=FineTuningOptions(max_epochs=2, batch_size=16, patience=1),
            refinement=RefinementOptions(cycles=1),
        )
    )

    assert summary.epochs_ran >= 1
    assert project.test_metrics is not None
    preds = project.predict(frame[["x1", "x2", "x3"]].head(3))
    assert preds.shape == (3, 1)


def test_project_deep_dual_path_manifest_shape() -> None:
    rng = np.random.default_rng(23)
    x1 = rng.uniform(0.0, 1.0, size=48)
    x2 = rng.uniform(0.0, 1.0, size=48)
    x3 = rng.uniform(0.0, 1.0, size=48)
    y = 0.4 * x1 + 0.25 * x2 + 0.15 * x3
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "y": y})

    project = Project(name="deep-dual-path", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.apply_workspace_template("deep_dual_path")

    spec = project.model_spec
    assert spec is not None
    assert spec.decision_input_mode == "raw_and_all_stages"
    assert len(spec.decision_layer.variables) > len(project.variables)


def test_project_deep_dual_raw_final_manifest_shape() -> None:
    rng = np.random.default_rng(29)
    x1 = rng.uniform(0.0, 1.0, size=48)
    x2 = rng.uniform(0.0, 1.0, size=48)
    x3 = rng.uniform(0.0, 1.0, size=48)
    y = 0.5 * x1 + 0.1 * x2 + 0.2 * x3
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "y": y})

    project = Project(name="deep-dual-raw-final", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.apply_workspace_template("deep_dual_raw_final")

    spec = project.model_spec
    assert spec is not None
    assert spec.decision_input_mode == "raw_and_final"
    final_stage_concepts = sum(block.n_concepts for block in spec.stages[-1].blocks)
    assert len(spec.decision_layer.variables) == len(project.variables) + final_stage_concepts


def test_project_deep_dual_context_manifest_shape() -> None:
    rng = np.random.default_rng(31)
    x1 = rng.uniform(0.0, 1.0, size=48)
    x2 = rng.uniform(0.0, 1.0, size=48)
    x3 = rng.uniform(0.0, 1.0, size=48)
    x4 = rng.uniform(0.0, 1.0, size=48)
    y = 0.3 * x1 + 0.2 * x2 + 0.2 * x3 + 0.1 * x4
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "y": y})

    project = Project(name="deep-dual-context", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.apply_workspace_template("deep_dual_path_block3")

    spec = project.model_spec
    assert spec is not None
    assert spec.decision_input_mode == "raw_and_all_stages"
    assert len(spec.stages[0].blocks[0].input_indices) == 3


def test_project_deep_dual_shortcut_dashboard_supports_raw_inputs() -> None:
    rng = np.random.default_rng(37)
    x1 = rng.uniform(0.0, 1.0, size=64)
    x2 = rng.uniform(0.0, 1.0, size=64)
    x3 = rng.uniform(0.0, 1.0, size=64)
    y = 0.45 * x1 + 0.25 * x2 * x3
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "y": y})

    project = Project(name="deep-dual-shortcut-dashboard", task_type="regression")
    project.from_dataframe(frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    project.apply_workspace_template("deep_dual_raw_final")
    summary = project.train(
        ModelTrainingConfig(
            task_type=TaskType.REGRESSION,
            use_stagewise_pretraining=True,
            use_bootstrap_initialization=True,
            stagewise=StagewiseOptions(epochs_per_stage=1, decision_epochs=1, refinement_rounds=1),
            fine_tuning=FineTuningOptions(max_epochs=2, batch_size=16, patience=1),
            refinement=RefinementOptions(cycles=1),
        )
    )

    assert summary.epochs_ran >= 1
    dashboard = project.dashboard(frame[["x1", "x2", "x3"]].head(1))
    assert len(dashboard) == 1
    assert dashboard[0].decision_concept_contributions
    chain_text = project.rule_chain_flow(frame[["x1", "x2", "x3"]].head(1), as_text=True)
    assert "SAMPLE 0" in chain_text
