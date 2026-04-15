import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from ruflex.core.enums import TaskType
from ruflex.toolbox import (
    article_benchmark_plan,
    apply_model_preset,
    apply_model_preset_from_exported_study,
    apply_workspace_template,
    auto_variable,
    attach_dataframe,
    best_exported_study,
    clear_all_rule_bases,
    clear_experiment_history,
    clear_study_run_history,
    concept_flow,
    configure_flat_model,
    rank_exported_studies,
    run_article_benchmark,
    dashboard,
    default_training_config,
    experiment_history,
    compare_exported_studies,
    format_function_catalog,
    export_study_run_artifacts,
    gaussian_mf,
    get_block_rule_base,
    get_decision_rule_base,
    get_variable,
    infer_variables,
    list_exported_studies,
    list_article_benchmark_runs,
    list_study_pipelines,
    list_training_presets,
    list_rule_targets,
    list_functions,
    list_workspace_templates,
    make_antecedent,
    make_rule,
    make_rule_base,
    make_rule_template,
    make_variable,
    model_preset,
    model_report,
    new_project,
    predict,
    prepare_article_materials,
    load_exported_study,
    load_article_benchmark,
    load_rule_base_catalog,
    load_project_from_exported_study,
    load_variable_catalog,
    rule_base_catalog,
    save_rule_base_catalog,
    save_variable_catalog,
    run_study_pipeline,
    set_block_rule_base,
    set_decision_rule_base,
    set_rule_base_catalog,
    set_variable,
    set_variable_catalog,
    study_pipeline,
    study_run_history,
    summary,
    training_preset,
    train,
    variable_catalog,
)


def test_toolbox_workflow_smoke():
    rng = np.random.default_rng(123)
    x1 = rng.uniform(0.0, 1.0, size=48)
    x2 = rng.uniform(0.0, 1.0, size=48)
    y = 0.65 * x1 + 0.25 * x2
    frame = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

    project = new_project("toolbox-smoke", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    infer_variables(project, term_count=3)
    configure_flat_model(project, max_rules=4)
    training_config = default_training_config(project, stagewise=False, max_epochs=2, batch_size=16)

    training_summary = train(project, training_config=training_config)
    assert training_summary.epochs_ran >= 1

    preds = predict(project, frame[["x1", "x2"]].head(4))
    assert preds.shape == (4, 1)

    dash = dashboard(project, frame[["x1", "x2"]].head(1))
    assert len(dash) == 1

    report = model_report(project)
    assert "MODEL REPORT" in report

    flow_text = concept_flow(project, frame[["x1", "x2"]].head(1), as_text=True)
    assert "SAMPLE 0" in flow_text

    auto_built = auto_variable("manual_x", (0.0, 1.0), term_count=3)
    explicit = make_variable(
        "manual_y",
        gaussian_mf((0.2, 0.5, 0.8), (0.1, 0.1, 0.1), term_names=("low", "mid", "high")),
        value_range=(0.0, 1.0),
    )
    assert auto_built.name == "manual_x"
    assert explicit.term_names == ("low", "mid", "high")

    functions = list_functions()
    assert any(item.name == "train" for item in functions)
    assert any(item.name == "gaussian_mf" for item in functions)
    assert "RUFLEX TOOLBOX FUNCTIONS" in format_function_catalog()

    updated_x1 = make_variable(
        "x1",
        gaussian_mf((0.15, 0.5, 0.85), (0.12, 0.12, 0.12), term_names=("low", "mid", "high")),
        value_range=(0.0, 1.0),
    )
    set_variable(project, "x1", updated_x1)
    assert get_variable(project, "x1").term_names == ("low", "mid", "high")
    assert variable_catalog(project)["x1"]["membership"]["term_names"] == ["low", "mid", "high"]
    assert summary(project)["has_model"] is False

    targets = list_rule_targets(project)
    hidden_target = next(target for target in targets if target["layer_kind"] == "hidden")
    decision_target = next(target for target in targets if target["layer_kind"] == "decision")
    assert hidden_target["variable_terms"]["x1"] == ("low", "mid", "high")
    assert hidden_target["max_rules"] == 4
    assert decision_target["max_rule_arity"] is not None

    hidden_rule_base = make_rule_base(
        (
            make_rule(
                "flat_hidden_rule_1",
                (
                    make_antecedent("x1", "low"),
                    make_antecedent("x2", get_variable(project, "x2").term_names[0]),
                ),
                consequent={hidden_target["output_names"][0]: 0.8},
                layer_name=hidden_target["block_name"],
            ),
        )
    )
    set_block_rule_base(project, hidden_target["block_name"], hidden_rule_base, stage_name=hidden_target["stage_name"])

    decision_rule_base = make_rule_template(
        project,
        block_name=decision_target["block_name"],
        layer_kind="decision",
    )
    set_decision_rule_base(project, decision_rule_base)

    assert get_block_rule_base(project, hidden_target["block_name"], stage_name=hidden_target["stage_name"]) is not None
    assert get_decision_rule_base(project) is not None
    assert sum(value is not None for value in rule_base_catalog(project).values()) == 2

    clear_all_rule_bases(project)
    assert all(value is None for value in rule_base_catalog(project).values())


def test_toolbox_catalog_io_roundtrip(tmp_path):
    rng = np.random.default_rng(99)
    x1 = rng.uniform(0.0, 1.0, size=16)
    x2 = rng.uniform(0.0, 1.0, size=16)
    y = 0.5 * x1 + 0.2 * x2
    frame = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

    project = new_project("catalog-io", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    infer_variables(project, term_count=3)
    configure_flat_model(project, max_rules=4)

    variable_payload = variable_catalog(project)
    variable_path = tmp_path / "variables.json"
    save_variable_catalog(project, variable_path)

    project.set_variable(
        "x1",
        make_variable(
            "x1",
            gaussian_mf((0.1, 0.5, 0.9), (0.2, 0.2, 0.2), term_names=("a", "b", "c")),
            value_range=(0.0, 1.0),
        ),
    )
    set_variable_catalog(project, variable_payload)
    assert get_variable(project, "x1").term_names == ("term_1", "term_2", "term_3")

    project.set_variable(
        "x1",
        make_variable(
            "x1",
            gaussian_mf((0.1, 0.5, 0.9), (0.2, 0.2, 0.2), term_names=("a", "b", "c")),
            value_range=(0.0, 1.0),
        ),
    )
    load_variable_catalog(project, variable_path)
    assert get_variable(project, "x1").term_names == ("term_1", "term_2", "term_3")

    targets = list_rule_targets(project)
    hidden_target = next(target for target in targets if target["layer_kind"] == "hidden")
    decision_target = next(target for target in targets if target["layer_kind"] == "decision")
    hidden_rule_base = make_rule_base(
        (
            make_rule(
                "catalog_hidden_rule_1",
                (
                    make_antecedent("x1", get_variable(project, "x1").term_names[0]),
                    make_antecedent("x2", get_variable(project, "x2").term_names[0]),
                ),
                consequent={hidden_target["output_names"][0]: 0.7},
                layer_name=hidden_target["block_name"],
            ),
        )
    )
    decision_rule_base = make_rule_template(project, block_name=decision_target["block_name"], layer_kind="decision")
    set_block_rule_base(project, hidden_target["block_name"], hidden_rule_base, stage_name=hidden_target["stage_name"])
    set_decision_rule_base(project, decision_rule_base)

    rule_catalog_payload = rule_base_catalog(project)
    rule_catalog_path = tmp_path / "rule_bases.json"
    save_rule_base_catalog(project, rule_catalog_path)

    clear_all_rule_bases(project)
    assert all(value is None for value in rule_base_catalog(project).values())

    set_rule_base_catalog(project, rule_catalog_payload)
    assert get_decision_rule_base(project) is not None

    clear_all_rule_bases(project)
    load_rule_base_catalog(project, rule_catalog_path)
    assert get_block_rule_base(project, hidden_target["block_name"], stage_name=hidden_target["stage_name"]) is not None


def test_model_preset_and_experiment_history():
    rng = np.random.default_rng(17)
    x1 = rng.uniform(0.0, 1.0, size=32)
    x2 = rng.uniform(0.0, 1.0, size=32)
    y = 0.55 * x1 + 0.15 * x2
    frame = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

    project = new_project("preset-history", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    infer_variables(project, term_count=3)
    configure_flat_model(project, max_rules=4)

    preset = model_preset(project)
    clone = new_project("preset-clone", task_type=TaskType.REGRESSION)
    attach_dataframe(clone, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    apply_model_preset(clone, preset)
    assert clone.model_kind == project.model_kind
    assert tuple(variable.name for variable in clone.variables) == ("x1", "x2")

    training_config = default_training_config(project, stagewise=False, max_epochs=2, batch_size=16)
    train(project, training_config=training_config)
    history = experiment_history(project)
    assert len(history) >= 1
    assert history[-1]["model_kind"] == "flat_neuro_fuzzy"

    clear_experiment_history(project)
    assert experiment_history(project) == ()


def test_workspace_templates_and_training_presets():
    rng = np.random.default_rng(31)
    x1 = rng.uniform(0.0, 1.0, size=24)
    x2 = rng.uniform(0.0, 1.0, size=24)
    x3 = rng.uniform(0.0, 1.0, size=24)
    x4 = rng.uniform(0.0, 1.0, size=24)
    y = 0.3 * x1 + 0.2 * x2 + 0.1 * x3 + 0.1 * x4
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "y": y})

    project = new_project("template-preset", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)

    workspace_templates = list_workspace_templates(project)
    assert any(item["name"] == "deep_article_demo" for item in workspace_templates)

    apply_workspace_template(project, "deep_compact")
    assert project.model_kind == "deep_fuzzy_feature_learning"
    assert len(project.variables) == 4

    training_presets = list_training_presets(project)
    assert any(item["name"] == "balanced" for item in training_presets)

    preset_config = training_preset(project, "fast_debug")
    assert preset_config.use_stagewise_pretraining is False
    assert preset_config.fine_tuning.max_epochs == 8


def test_study_pipelines():
    rng = np.random.default_rng(77)
    x1 = rng.uniform(0.0, 1.0, size=32)
    x2 = rng.uniform(0.0, 1.0, size=32)
    x3 = rng.uniform(0.0, 1.0, size=32)
    y = 0.4 * x1 + 0.2 * x2 + 0.1 * x3
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "y": y})

    project = new_project("study-pipelines", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)

    pipelines = list_study_pipelines(project)
    assert any(item["name"] == "quick_smoke" for item in pipelines)

    pipeline_spec = study_pipeline(project, "quick_smoke")
    assert pipeline_spec["workspace_template"] == "deep_compact"

    result = run_study_pipeline(project, "quick_smoke")
    assert result["pipeline_name"] == "quick_smoke"
    assert project.model_kind == "deep_fuzzy_feature_learning"
    assert len(study_run_history(project)) == 1

    clear_study_run_history(project)
    assert study_run_history(project) == ()


def test_study_run_artifact_export(tmp_path):
    rng = np.random.default_rng(117)
    x1 = rng.uniform(0.0, 1.0, size=32)
    x2 = rng.uniform(0.0, 1.0, size=32)
    x3 = rng.uniform(0.0, 1.0, size=32)
    y = 0.45 * x1 + 0.15 * x2 + 0.1 * x3
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "y": y})

    project = new_project("study-artifacts", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    pipeline_record = run_study_pipeline(project, "quick_smoke", export_root=tmp_path / "auto_experiments")
    assert "artifact_export" in pipeline_record
    assert Path(pipeline_record["artifact_export"]["export_dir"]).exists()

    export_payload = export_study_run_artifacts(project, tmp_path / "experiments")
    export_dir = Path(export_payload["export_dir"])
    assert export_dir.exists()
    assert export_dir.name.endswith("quick_smoke")

    expected_files = {
        "study_run",
        "metrics",
        "project_manifest",
        "project_summary",
        "dataset_summary",
        "training_config",
        "model_preset",
        "rule_base_catalog",
        "variable_catalog",
        "study_pipeline",
        "project_report",
        "model_report",
        "project_bundle",
    }
    assert expected_files.issubset(export_payload["files"])

    metrics_payload = json.loads((export_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "train_metrics" in metrics_payload
    assert "test_metrics" in metrics_payload

    project_manifest = json.loads((export_dir / "project_manifest.json").read_text(encoding="utf-8"))
    assert project_manifest["name"] == "study-artifacts"

    exported = list_exported_studies(project, tmp_path / "experiments")
    assert len(exported) == 1
    assert exported[0]["pipeline_name"] == "quick_smoke"

    comparison = compare_exported_studies(project, tmp_path / "experiments")
    assert len(comparison) == 1
    assert comparison[0]["pipeline_name"] == "quick_smoke"
    assert comparison[0]["directory_name"] == export_dir.name

    loaded = load_exported_study(project, export_dir)
    assert loaded["study_run"]["pipeline_name"] == "quick_smoke"
    assert loaded["project_summary"]["name"] == "study-artifacts"
    assert loaded["project_report"] is not None
    assert "project_bundle" in loaded["available_directories"]

    restored_from_bundle = load_project_from_exported_study(export_dir)
    assert restored_from_bundle.name == "study-artifacts"
    assert restored_from_bundle.model is not None
    restored_project = load_project_from_exported_study(export_dir, frame=frame)
    assert restored_project.name == "study-artifacts"
    assert restored_project.model_kind == "deep_fuzzy_feature_learning"
    assert restored_project.target_name == "y"
    assert tuple(variable.name for variable in restored_project.variables) == ("x1", "x2", "x3")

    stronger_export_dir = export_dir.parent / f"{export_dir.name}_better"
    shutil.copytree(export_dir, stronger_export_dir)
    stronger_study_run = json.loads((stronger_export_dir / "study_run.json").read_text(encoding="utf-8"))
    stronger_study_run["timestamp_utc"] = "2099-01-01T00:00:00+00:00"
    stronger_study_run["test_metrics"]["rmse"] = 0.0
    stronger_study_run["test_metrics"]["mse"] = 0.0
    (stronger_export_dir / "study_run.json").write_text(json.dumps(stronger_study_run, indent=2), encoding="utf-8")

    stronger_metrics = json.loads((stronger_export_dir / "metrics.json").read_text(encoding="utf-8"))
    stronger_metrics["test_metrics"]["rmse"] = 0.0
    stronger_metrics["test_metrics"]["mse"] = 0.0
    (stronger_export_dir / "metrics.json").write_text(json.dumps(stronger_metrics, indent=2), encoding="utf-8")

    ranked = rank_exported_studies(project, tmp_path / "experiments", metric_name="rmse")
    assert ranked[0]["directory_name"] == stronger_export_dir.name
    assert ranked[0]["ranking_split"] == "test"
    assert ranked[0]["ranking_value"] == 0.0

    best = best_exported_study(project, tmp_path / "experiments", metric_name="rmse")
    assert best["directory_name"] == stronger_export_dir.name

    preset_clone = new_project("preset-clone-from-export", task_type=TaskType.REGRESSION)
    attach_dataframe(preset_clone, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)
    apply_model_preset_from_exported_study(preset_clone, best["export_dir"])
    assert preset_clone.model_kind == "deep_fuzzy_feature_learning"
    assert tuple(variable.name for variable in preset_clone.variables) == ("x1", "x2", "x3")


def test_article_benchmark_runner(tmp_path):
    rng = np.random.default_rng(231)
    x1 = rng.uniform(0.0, 1.0, size=36)
    x2 = rng.uniform(0.0, 1.0, size=36)
    x3 = rng.uniform(0.0, 1.0, size=36)
    x4 = rng.uniform(0.0, 1.0, size=36)
    y = 0.35 * x1 + 0.2 * x2 + 0.1 * x3 + 0.1 * x4
    frame = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "x4": x4, "y": y})

    project = new_project("article-benchmark", task_type=TaskType.REGRESSION)
    attach_dataframe(project, frame, target_column="y", validation_fraction=0.1, test_fraction=0.1)

    plan = article_benchmark_plan(project)
    assert any(item["study_pipeline"] == "flat_baseline_benchmark" for item in plan)
    assert any(item["study_pipeline"] == "deep_article_demo" for item in plan)

    benchmark = run_article_benchmark(
        project,
        output_root=tmp_path / "article_benchmark",
        variant_names=("flat_baseline", "deep_article_demo"),
        training_preset_override="fast_debug",
        seeds=(11, 13),
    )
    benchmark_dir = Path(benchmark["benchmark_dir"])
    assert benchmark_dir.exists()
    assert benchmark["seed_count"] == 2
    assert benchmark["seeds"] == [11, 13]
    assert len(benchmark["results"]) >= 5
    assert (benchmark_dir / "benchmark_plan.json").exists()
    assert (benchmark_dir / "benchmark_results.json").exists()
    assert (benchmark_dir / "benchmark_results.csv").exists()
    assert (benchmark_dir / "benchmark_per_seed_results.csv").exists()
    assert (benchmark_dir / "benchmark_report.md").exists()
    assert any(row["family"] == "sklearn" for row in benchmark["results"])
    assert any(row["family"] == "ruflex" for row in benchmark["results"])
    assert all(
        Path(row["export_dir"]).exists()
        for row in benchmark["results"]
        if row["family"] == "ruflex"
    )

    listed_runs = list_article_benchmark_runs(tmp_path / "article_benchmark")
    assert len(listed_runs) == 1
    assert listed_runs[0]["directory_name"] == benchmark_dir.name
    assert listed_runs[0]["seed_count"] == 2

    loaded_benchmark = load_article_benchmark(benchmark_dir)
    assert loaded_benchmark["source_project"]["name"] == "article-benchmark"
    assert loaded_benchmark["seed_count"] == 2
    assert len(loaded_benchmark["results"]) >= 5
    assert loaded_benchmark["per_seed_results"]

    materials = prepare_article_materials(benchmark_dir, output_root=tmp_path / "article_assets")
    materials_dir = Path(materials["output_dir"])
    assert materials_dir.exists()
    assert (materials_dir / "benchmark_results.json").exists()
    assert (materials_dir / "results_table.csv").exists()
    assert (materials_dir / "results_table.md").exists()
    assert (materials_dir / "per_seed_results_table.csv").exists()
    assert (materials_dir / "artifact_index.json").exists()
    assert (materials_dir / "article_summary.md").exists()
    assert (materials_dir / "results_overview.png").exists()
    assert (materials_dir / "best_training_history.png").exists()
    assert (materials_dir / "best_sample_top_rules.png").exists()
    assert (materials_dir / "best_sample_hidden_concepts.png").exists()
    assert (materials_dir / "best_sample_decision_concepts.png").exists()
    assert (materials_dir / "best_sample_fuzzification.png").exists()
    assert (materials_dir / "best_sample_concept_flow.txt").exists()
    assert (materials_dir / "best_sample_rule_chain.txt").exists()
