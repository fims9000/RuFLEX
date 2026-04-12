from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ruflex.toolbox import (
    attach_dataframe,
    concept_flow,
    configure_deep_model,
    dashboard,
    export_study_run_artifacts,
    format_function_catalog,
    infer_variables,
    model_report,
    new_project,
    predict,
    project_report,
    run_study_pipeline,
    train,
)


def main() -> None:
    rng = np.random.default_rng(21)
    samples = 128
    x1 = rng.uniform(0.0, 1.0, size=samples)
    x2 = rng.uniform(0.0, 1.0, size=samples)
    x3 = rng.uniform(0.0, 1.0, size=samples)
    x4 = rng.uniform(0.0, 1.0, size=samples)
    y = 0.4 * np.sin(np.pi * x1 * x2) + 0.35 * (x3 * x4) + 0.1 * x1

    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "y": y})

    project = new_project("toolbox-demo")
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.15, test_fraction=0.15)
    infer_variables(project, term_count=3)
    configure_deep_model(project, block_size=2, hidden_stage_count=2, concept_width=2, max_rules=4)
    train(project)

    print(format_function_catalog().splitlines()[0])
    print(project_report(project))
    print()
    print(model_report(project))
    print()
    print(predict(project, frame[["x1", "x2", "x3", "x4"]].head(3)))
    print()
    print(concept_flow(project, frame[["x1", "x2", "x3", "x4"]].head(1), as_text=True))
    print()
    print(dashboard(project, frame[["x1", "x2", "x3", "x4"]].head(1))[0].to_dict())
    print()

    study_project = new_project("toolbox-study-demo")
    attach_dataframe(study_project, frame, target_column="y", validation_fraction=0.15, test_fraction=0.15)
    study_record = run_study_pipeline(study_project, "quick_smoke")
    print(study_record["pipeline_name"])
    print(export_study_run_artifacts(study_project, Path("experiments"))["export_dir"])


if __name__ == "__main__":
    main()
