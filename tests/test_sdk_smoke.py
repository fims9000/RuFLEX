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
