from __future__ import annotations

import numpy as np
import pandas as pd

from ruflex.core.enums import TaskType
from ruflex.sdk.project import Project
from ruflex.training.config import FineTuningOptions, ModelTrainingConfig, RefinementOptions, StagewiseOptions


def main() -> None:
    rng = np.random.default_rng(7)
    samples = 256
    x1 = rng.uniform(0.0, 1.0, size=samples)
    x2 = rng.uniform(0.0, 1.0, size=samples)
    x3 = rng.uniform(0.0, 1.0, size=samples)
    x4 = rng.uniform(0.0, 1.0, size=samples)
    y = (
        0.45 * np.sin(np.pi * x1 * x2)
        + 0.30 * (x3 * x4)
        + 0.15 * x1
    )

    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "y": y})

    project = Project(name="deep-demo", task_type=TaskType.REGRESSION.value)
    project.from_dataframe(frame, target_column="y", validation_fraction=0.15, test_fraction=0.15)
    project.infer_variables(term_count=3)
    project.configure_model(
        "deep_fuzzy_feature_learning",
        block_size=2,
        hidden_stage_count=2,
        concept_width=2,
        max_rule_arity=2,
        max_rules=4,
    )

    summary = project.train(
        ModelTrainingConfig(
            task_type=TaskType.REGRESSION,
            use_stagewise_pretraining=True,
            stagewise=StagewiseOptions(
                epochs_per_stage=10,
                decision_epochs=10,
                refinement_rounds=1,
                batch_size=64,
            ),
            fine_tuning=FineTuningOptions(
                max_epochs=20,
                batch_size=64,
                patience=5,
                learning_rate=1e-3,
            ),
            refinement=RefinementOptions(cycles=1),
        )
    )

    print("Project summary:")
    print(project.summary())
    print("Training source:", summary.source)
    print("Train metrics:", summary.train_metrics)
    print("Validation metrics:", summary.validation_metrics)
    print("Test metrics:", project.test_metrics)
    print()
    print("Model report:")
    print(project.model_report())
    print()
    print("Sample explanations:")
    print(project.explain(frame[["x1", "x2", "x3", "x4"]].head(2), top_k_rules=2, as_text=True))
    print()
    print("Concept flow:")
    print(project.concept_flow(frame[["x1", "x2", "x3", "x4"]].head(1), top_k_rules=2, as_text=True))


if __name__ == "__main__":
    main()
