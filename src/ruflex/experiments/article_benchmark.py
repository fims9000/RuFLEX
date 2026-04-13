from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ruanfis.benchmarks import (
    BenchmarkEntryResult,
    aggregate_benchmark_results,
    evaluate_trained_model,
    run_tabular_benchmark,
    serialize_aggregated_benchmark_results,
    serialize_benchmark_results,
)
from ruflex.io.project import load_manifest, save_manifest
from ruflex.sdk.project import Project
from ruflex.training.config import ModelTrainingConfig
from ruflex.visualization.plots import plot_membership_functions, plot_training_history


@dataclass(frozen=True)
class ArticleBenchmarkVariant:
    name: str
    label: str
    article_role: str
    description: str
    workspace_template: str
    training_preset: str
    study_pipeline: str | None = None
    workspace_overrides: dict[str, Any] | None = None
    training_overrides: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "article_role": self.article_role,
            "description": self.description,
            "workspace_template": self.workspace_template,
            "training_preset": self.training_preset,
            "study_pipeline": self.study_pipeline,
            "workspace_overrides": None if self.workspace_overrides is None else dict(self.workspace_overrides),
            "training_overrides": None if self.training_overrides is None else dict(self.training_overrides),
        }


def article_benchmark_plan(project: Project) -> tuple[dict[str, Any], ...]:
    _require_project_dataset(project)
    shortcut_template = _workspace_template(project, "deep_dual_raw_final")
    shortcut_stage_count = int(shortcut_template["config"]["hidden_stage_count"])

    variants = [
        ArticleBenchmarkVariant(
            name="flat_baseline",
            label="Flat Baseline",
            article_role="baseline",
            description="Reference flat neuro-fuzzy baseline for the main comparison table.",
            workspace_template="flat_baseline",
            training_preset="balanced",
            study_pipeline="flat_baseline_benchmark",
        ),
        ArticleBenchmarkVariant(
            name="flat_interpretable",
            label="Flat Interpretable",
            article_role="interpretable_baseline",
            description="Compact interpretable flat model with stronger structure-aware regularization.",
            workspace_template="flat_interpretable",
            training_preset="interpretable",
            study_pipeline="interpretable_flat_study",
        ),
    ]

    if shortcut_stage_count > 1:
        variants.append(
            ArticleBenchmarkVariant(
                name="deep_stage1_ablation",
                label="Deep Depth 1",
                article_role="depth_ablation",
                description="Depth ablation of the shortcut deep architecture with a single hidden concept stage.",
                workspace_template="deep_dual_raw_final",
                training_preset="article_demo",
                workspace_overrides={"config": {"hidden_stage_count": 1}},
            )
        )

    variants.extend(
        [
            ArticleBenchmarkVariant(
                name="deep_article_demo",
                label="Sequential Deep Reference",
                article_role="sequential_deep_reference",
                description="Legacy sequential deep fuzzy configuration without shortcut access to raw features.",
                workspace_template="deep_article_demo",
                training_preset="article_demo",
                study_pipeline="deep_article_demo",
            ),
            ArticleBenchmarkVariant(
                name="deep_dual_path",
                label="Deep Dual Path",
                article_role="all_stage_shortcut_model",
                description="Overlapping deep fuzzy architecture with direct access to raw features and all hidden stages.",
                workspace_template="deep_dual_path",
                training_preset="article_demo",
                study_pipeline="deep_dual_path_study",
            ),
            ArticleBenchmarkVariant(
                name="deep_dual_raw_final",
                label="Deep Dual Shortcut",
                article_role="primary_deep_model",
                description="Shortcut deep fuzzy architecture with raw features and the final hidden stage routed directly to the decision layer.",
                workspace_template="deep_dual_raw_final",
                training_preset="article_demo",
                study_pipeline="deep_dual_shortcut_study",
            ),
            ArticleBenchmarkVariant(
                name="deep_dual_path_block3",
                label="Deep Dual Context",
                article_role="context_enriched_deep_model",
                description="Shortcut deep fuzzy architecture with overlapping three-feature blocks for richer local interactions.",
                workspace_template="deep_dual_path_block3",
                training_preset="article_demo",
                study_pipeline="deep_dual_context_study",
            ),
        ]
    )

    deduplicated: list[ArticleBenchmarkVariant] = []
    seen_names: set[str] = set()
    for variant in variants:
        if variant.name in seen_names:
            continue
        seen_names.add(variant.name)
        deduplicated.append(variant)
    return tuple(item.to_dict() for item in deduplicated)


def run_article_benchmark(
    project: Project,
    *,
    output_root: str | Path = "experiments/article_benchmark",
    variant_names: tuple[str, ...] | list[str] | None = None,
    training_preset_override: str | None = None,
    seeds: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
    _require_project_dataset(project)

    benchmark_dir = _benchmark_directory(output_root=output_root, project_name=project.name)
    benchmark_dir.mkdir(parents=True, exist_ok=False)
    runs_root = benchmark_dir / "runs"
    runs_root.mkdir(exist_ok=True)

    plan = article_benchmark_plan(project)
    selected_plan = _select_variants(plan, variant_names)
    resolved_seeds = _resolve_seeds(seeds)

    per_seed_rows: list[dict[str, Any]] = []
    per_seed_entries: list[tuple[BenchmarkEntryResult, ...]] = []
    for seed in resolved_seeds:
        seed_payload = _run_benchmark_seed(
            project,
            selected_plan=selected_plan,
            seed=seed,
            runs_root=runs_root,
            training_preset_override=training_preset_override,
        )
        per_seed_rows.extend(seed_payload["rows"])
        per_seed_entries.append(seed_payload["entries"])

    aggregated = aggregate_benchmark_results(per_seed_entries)
    metadata_by_model = _aggregate_row_metadata(project.task_type, per_seed_rows)
    results = [
        _aggregated_result_row(item, metadata_by_model.get(item.model_name, {}))
        for item in aggregated
    ]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_project": {
            "name": project.name,
            "task_type": project.task_type,
            "target_name": project.target_name,
            "feature_names": list(project.feature_names),
            "dataset_summary": project.dataset_summary(),
        },
        "benchmark_dir": str(benchmark_dir),
        "runs_root": str(runs_root),
        "variant_plan": [dict(item) for item in selected_plan],
        "training_preset_override": training_preset_override,
        "seeds": list(resolved_seeds),
        "seed_count": len(resolved_seeds),
        "baseline_models": _baseline_model_names(per_seed_rows),
        "results": results,
        "per_seed_results": per_seed_rows,
        "aggregated_results": list(serialize_aggregated_benchmark_results(aggregated)),
        "serialized_per_seed_results": [
            {
                "seed": seed,
                "results": list(serialize_benchmark_results(seed_results)),
            }
            for seed, seed_results in zip(resolved_seeds, per_seed_entries, strict=True)
        ],
    }

    save_manifest(summary, benchmark_dir / "benchmark_results.json")
    save_manifest(
        {
            "variants": [dict(item) for item in selected_plan],
            "seeds": list(resolved_seeds),
        },
        benchmark_dir / "benchmark_plan.json",
    )
    _write_results_csv(results, benchmark_dir / "benchmark_results.csv")
    _write_results_csv(per_seed_rows, benchmark_dir / "benchmark_per_seed_results.csv")
    (benchmark_dir / "benchmark_report.md").write_text(_benchmark_report(summary), encoding="utf-8")
    return summary


def list_article_benchmark_runs(root_dir: str | Path = "experiments/article_benchmark") -> tuple[dict[str, Any], ...]:
    root = Path(root_dir).expanduser().resolve()
    if not root.exists():
        return ()
    rows = []
    for candidate in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True):
        results_path = candidate / "benchmark_results.json"
        if not results_path.exists():
            continue
        payload = load_manifest(results_path)
        rows.append(
            {
                "benchmark_dir": str(candidate),
                "directory_name": candidate.name,
                "generated_at_utc": payload.get("generated_at_utc"),
                "source_project_name": payload.get("source_project", {}).get("name"),
                "task_type": payload.get("source_project", {}).get("task_type"),
                "target_name": payload.get("source_project", {}).get("target_name"),
                "variant_count": len(payload.get("variant_plan", ())),
                "model_count": len(payload.get("results", ())),
                "seed_count": int(payload.get("seed_count", 1)),
                "training_preset_override": payload.get("training_preset_override"),
            }
        )
    return tuple(rows)


def load_article_benchmark(benchmark_dir: str | Path) -> dict[str, Any]:
    root = Path(benchmark_dir).expanduser().resolve()
    results_path = root / "benchmark_results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"Article benchmark is missing benchmark_results.json: {root}")
    return load_manifest(results_path)


def prepare_article_materials(
    benchmark_dir: str | Path,
    *,
    output_root: str | Path = "docs/article/assets",
) -> dict[str, Any]:
    benchmark_root = Path(benchmark_dir).expanduser().resolve()
    summary = load_article_benchmark(benchmark_root)
    output_dir = Path(output_root).expanduser().resolve() / benchmark_root.name
    output_dir.mkdir(parents=True, exist_ok=True)

    results = list(summary.get("results", ()))
    per_seed_results = list(summary.get("per_seed_results", ()))
    files: dict[str, str] = {}

    benchmark_results_path = output_dir / "benchmark_results.json"
    save_manifest(summary, benchmark_results_path)
    files["benchmark_results"] = str(benchmark_results_path)

    results_csv_path = output_dir / "results_table.csv"
    _write_results_csv(results, results_csv_path)
    files["results_table_csv"] = str(results_csv_path)

    results_md_path = output_dir / "results_table.md"
    results_md_path.write_text(
        _markdown_table(
            headers=_report_headers(results),
            rows=[{header: row.get(header) for header in _report_headers(results)} for row in results],
        ),
        encoding="utf-8",
    )
    files["results_table_md"] = str(results_md_path)

    per_seed_csv_path = output_dir / "per_seed_results_table.csv"
    _write_results_csv(per_seed_results, per_seed_csv_path)
    files["per_seed_results_table_csv"] = str(per_seed_csv_path)

    artifact_index_path = output_dir / "artifact_index.json"
    save_manifest(
        {
            "benchmark_dir": str(benchmark_root),
            "artifacts": [
                {
                    "model_name": row.get("model_name"),
                    "model_label": row.get("model_label"),
                    "article_role": row.get("article_role"),
                    "study_pipeline": row.get("study_pipeline"),
                    "export_dir": row.get("export_dir"),
                    "best_seed": row.get("best_seed"),
                }
                for row in results
                if row.get("export_dir") is not None
            ],
        },
        artifact_index_path,
    )
    files["artifact_index"] = str(artifact_index_path)

    article_summary_path = output_dir / "article_summary.md"
    article_summary_path.write_text(_article_materials_summary(summary), encoding="utf-8")
    files["article_summary"] = str(article_summary_path)

    chart_path = _plot_article_results(summary, output_dir)
    if chart_path is not None:
        files["results_overview_chart"] = str(chart_path)

    files.update(_render_best_run_assets(summary, output_dir))

    benchmark_report_path = benchmark_root / "benchmark_report.md"
    if benchmark_report_path.exists():
        benchmark_report_copy = output_dir / "benchmark_report.md"
        benchmark_report_copy.write_text(benchmark_report_path.read_text(encoding="utf-8"), encoding="utf-8")
        files["benchmark_report"] = str(benchmark_report_copy)

    plan_path = benchmark_root / "benchmark_plan.json"
    if plan_path.exists():
        benchmark_plan_copy = output_dir / "benchmark_plan.json"
        save_manifest(load_manifest(plan_path), benchmark_plan_copy)
        files["benchmark_plan"] = str(benchmark_plan_copy)

    return {
        "benchmark_dir": str(benchmark_root),
        "output_dir": str(output_dir),
        "files": files,
        "model_count": len(results),
        "seed_count": int(summary.get("seed_count", 1)),
    }


def _require_project_dataset(project: Project) -> None:
    if project.dataset is None or project.dataset_config is None:
        raise RuntimeError("Attach a dataset before running the article benchmark.")


def _resolve_seeds(seeds: tuple[int, ...] | list[int] | None) -> tuple[int, ...]:
    if seeds is None:
        return (42,)
    resolved = tuple(int(seed) for seed in seeds)
    if not resolved:
        raise ValueError("Article benchmark seeds must not be empty.")
    return resolved


def _run_benchmark_seed(
    project: Project,
    *,
    selected_plan: tuple[dict[str, Any], ...],
    seed: int,
    runs_root: Path,
    training_preset_override: str | None,
) -> dict[str, Any]:
    split_project = _clone_project_for_benchmark(project, variant_name=f"seed_{seed}", random_state=seed)
    split = split_project.dataset.split(split_project.dataset_config)  # type: ignore[union-attr]

    baseline_entries = tuple(
        run_tabular_benchmark(
            train_inputs=torch.as_tensor(split.train_features, dtype=torch.float32),
            train_targets=torch.as_tensor(split.train_targets, dtype=torch.float32),
            test_inputs=torch.as_tensor(split.test_features, dtype=torch.float32),
            test_targets=torch.as_tensor(split.test_targets, dtype=torch.float32),
            task_type=project.task_type,
            fuzzy_models=None,
            random_state=seed,
        )
    )
    baseline_rows = [
        _seed_row_from_entry(seed=seed, entry=entry)
        for entry in baseline_entries
    ]

    variant_rows: list[dict[str, Any]] = []
    variant_entries: list[BenchmarkEntryResult] = []
    for variant in selected_plan:
        row, entry = _run_ruflex_variant(
            project,
            variant=variant,
            seed=seed,
            runs_root=runs_root,
            training_preset_override=training_preset_override,
        )
        variant_rows.append(row)
        variant_entries.append(entry)

    return {
        "rows": [*baseline_rows, *variant_rows],
        "entries": tuple([*baseline_entries, *variant_entries]),
    }


def _run_ruflex_variant(
    project: Project,
    *,
    variant: dict[str, Any],
    seed: int,
    runs_root: Path,
    training_preset_override: str | None,
) -> tuple[dict[str, Any], BenchmarkEntryResult]:
    benchmark_project = _clone_project_for_benchmark(project, variant_name=str(variant["name"]), random_state=seed)
    _apply_workspace_variant(benchmark_project, variant)
    artifact_pipeline_name = str(variant.get("study_pipeline") or variant["name"])

    resolved_training_preset = (
        str(training_preset_override)
        if training_preset_override is not None
        else str(variant["training_preset"])
    )
    training_config = benchmark_project.training_preset(resolved_training_preset)
    if variant.get("training_overrides") is not None:
        training_config = _merged_training_config(training_config, dict(variant["training_overrides"]))

    _set_global_seed(seed)
    summary = benchmark_project.train(training_config=training_config)

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline_name": artifact_pipeline_name,
        "pipeline_label": variant["label"],
        "workspace_template": variant["workspace_template"],
        "training_preset": resolved_training_preset,
        "training_preset_override": training_preset_override,
        "training_source": summary.source,
        "epochs_ran": int(summary.epochs_ran),
        "train_metrics": dict(summary.train_metrics),
        "validation_metrics": (
            None if summary.validation_metrics is None else dict(summary.validation_metrics)
        ),
        "test_metrics": None if benchmark_project.test_metrics is None else dict(benchmark_project.test_metrics),
        "training_config": training_config.to_dict(),
        "project_manifest": benchmark_project.to_manifest(),
        "project_summary": dict(benchmark_project.summary()),
        "dataset_summary": benchmark_project.dataset_summary(),
        "variable_catalog": benchmark_project.variable_catalog(),
        "rule_base_catalog": benchmark_project.rule_base_catalog(),
        "model_preset": benchmark_project.model_preset(),
        "project_report": benchmark_project.project_report(),
        "model_report": benchmark_project.model_report(),
        "study_pipeline": variant.get("study_pipeline"),
        "article_role": variant["article_role"],
    }
    history = list(benchmark_project.notes.get("study_run_history", ()))
    history.append(record)
    benchmark_project.notes["study_run_history"] = history
    export_payload = benchmark_project.export_study_run_artifacts(
        root_dir=runs_root,
        study_run_index=len(history) - 1,
    )
    record["artifact_export"] = export_payload
    history[-1] = record
    benchmark_project.notes["study_run_history"] = history

    split = benchmark_project.last_split
    backend_model = None if benchmark_project.model is None else benchmark_project.model.backend_model
    if split is None or backend_model is None:
        raise RuntimeError("Expected the benchmark project to expose a trained backend model and cached split.")

    evaluated = evaluate_trained_model(
        variant["name"],
        backend_model,
        task_type=project.task_type,
        train_inputs=torch.as_tensor(split.train_features, dtype=torch.float32),
        train_targets=torch.as_tensor(split.train_targets, dtype=torch.float32),
        test_inputs=torch.as_tensor(split.test_features, dtype=torch.float32),
        test_targets=torch.as_tensor(split.test_targets, dtype=torch.float32),
        family="ruflex",
        classification_threshold=training_config.fine_tuning.classification_threshold,
    )

    entry = BenchmarkEntryResult(
        model_name=str(variant["name"]),
        family="ruflex",
        train_metrics=dict(summary.train_metrics),
        test_metrics={} if benchmark_project.test_metrics is None else dict(benchmark_project.test_metrics),
        structural_metrics=dict(evaluated.structural_metrics),
        explainability_metrics=dict(evaluated.explainability_metrics),
        stability_artifacts=dict(evaluated.stability_artifacts),
    )

    row = {
        "seed": seed,
        "model_name": variant["name"],
        "model_label": variant["label"],
        "family": "ruflex",
        "article_role": variant["article_role"],
        "variant_name": variant["name"],
        "variant_label": variant["label"],
        "study_pipeline": variant.get("study_pipeline"),
        "workspace_template": variant["workspace_template"],
        "training_preset": resolved_training_preset,
        "training_preset_override": training_preset_override,
        "epochs_ran": int(summary.epochs_ran),
        "export_dir": export_payload["export_dir"],
    }
    row.update(_flatten_metric_block(dict(summary.train_metrics), "train"))
    row.update(_flatten_metric_block(dict(summary.validation_metrics or {}), "validation"))
    row.update(_flatten_metric_block(dict(benchmark_project.test_metrics or {}), "test"))
    row.update(_flatten_metric_block(dict(evaluated.structural_metrics), "structure"))
    row.update(_flatten_metric_block(dict(evaluated.explainability_metrics), "explainability"))
    return row, entry


def _clone_project_for_benchmark(
    project: Project,
    *,
    variant_name: str,
    random_state: int | None = None,
) -> Project:
    if project.dataset is None or project.dataset_config is None:
        raise RuntimeError("Attach a dataset before cloning a benchmark project.")
    config = project.dataset_config
    clone = Project(
        name=f"{project.name}-{variant_name}",
        task_type=project.task_type,
        description=project.description,
    )
    clone.from_dataframe(
        project.dataset.frame.copy(),
        target_column=config.target_column,
        feature_columns=config.feature_columns,
        validation_fraction=config.validation_fraction,
        test_fraction=config.test_fraction,
        normalization=config.normalization,
        fill_missing=config.fill_missing,
        random_state=config.random_state if random_state is None else int(random_state),
    )
    return clone


def _workspace_template(project: Project, template_name: str) -> dict[str, Any]:
    for item in project.list_workspace_templates():
        if item["name"] == template_name:
            return dict(item)
    raise KeyError(f"Unknown workspace template: {template_name!r}.")


def _apply_workspace_variant(project: Project, variant: dict[str, Any]) -> None:
    template = _workspace_template(project, str(variant["workspace_template"]))
    overrides = dict(variant.get("workspace_overrides") or {})
    config = dict(template["config"])
    if overrides.get("config") is not None:
        config = _merged_mapping(config, dict(overrides["config"]))
    term_count = int(overrides.get("term_count", template["term_count"]))
    membership_kind = str(overrides.get("membership_kind", template["membership_kind"]))
    mode = str(overrides.get("mode", template["mode"]))
    project.infer_variables(term_count=term_count, membership_kind=membership_kind)
    project.configure_model(mode, **config)


def _merged_training_config(
    training_config: ModelTrainingConfig,
    overrides: dict[str, Any],
) -> ModelTrainingConfig:
    payload = training_config.to_dict()
    merged = _merged_mapping(payload, overrides)
    return ModelTrainingConfig.from_dict(merged)


def _merged_mapping(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merged_mapping(dict(merged[key]), dict(value))
        else:
            merged[key] = value
    return merged


def _set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _select_variants(
    plan: tuple[dict[str, Any], ...],
    variant_names: tuple[str, ...] | list[str] | None,
) -> tuple[dict[str, Any], ...]:
    if variant_names is None:
        return tuple(plan)
    selected_names = tuple(str(name) for name in variant_names)
    selected = tuple(item for item in plan if item["name"] in selected_names)
    missing = [name for name in selected_names if name not in {item["name"] for item in plan}]
    if missing:
        raise ValueError(f"Unknown article benchmark variants: {missing}.")
    if not selected:
        raise ValueError("Article benchmark variant selection is empty.")
    return selected


def _flatten_metric_block(payload: dict[str, Any] | None, prefix: str) -> dict[str, Any]:
    if not payload:
        return {}
    return {f"{prefix}_{key}": value for key, value in payload.items()}


def _flatten_metric_summaries(payload: dict[str, Any], prefix: str) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, summary in payload.items():
        flattened[f"{prefix}_{key}_mean"] = float(summary.mean)
        flattened[f"{prefix}_{key}_std"] = float(summary.std)
    return flattened


def _benchmark_directory(*, output_root: str | Path, project_name: str) -> Path:
    root = Path(output_root).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).isoformat().replace(":", "-")
    slug = _slug(project_name)
    candidate = root / f"{_slug(timestamp)}_{slug}_article_benchmark"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        alternative = root / f"{_slug(timestamp)}_{slug}_article_benchmark_{index}"
        if not alternative.exists():
            return alternative
        index += 1


def _slug(value: str) -> str:
    slug = "".join(character if character.isalnum() else "_" for character in value.strip().lower())
    slug = slug.strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "artifact"


def _write_results_csv(results: list[dict[str, Any]], path: Path) -> None:
    fieldnames: list[str] = []
    for row in results:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def _aggregate_row_metadata(task_type: str, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["model_name"]), []).append(row)

    metadata: dict[str, dict[str, Any]] = {}
    for model_name, model_rows in grouped.items():
        best_seed_row = _best_seed_row(task_type, model_rows)
        first = model_rows[0]
        metadata[model_name] = {
            "model_label": first.get("model_label"),
            "family": first.get("family"),
            "article_role": first.get("article_role"),
            "variant_name": first.get("variant_name"),
            "variant_label": first.get("variant_label"),
            "study_pipeline": first.get("study_pipeline"),
            "workspace_template": first.get("workspace_template"),
            "training_preset": first.get("training_preset"),
            "training_preset_override": first.get("training_preset_override"),
            "seed_values": [int(item["seed"]) for item in model_rows],
            "best_seed": None if best_seed_row is None else best_seed_row.get("seed"),
            "export_dir": None if best_seed_row is None else best_seed_row.get("export_dir"),
        }
    return metadata


def _aggregated_result_row(result: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    row = {
        "model_name": result.model_name,
        "model_label": metadata.get("model_label") or _display_model_name(result.model_name),
        "family": result.family,
        "article_role": metadata.get("article_role"),
        "variant_name": metadata.get("variant_name"),
        "variant_label": metadata.get("variant_label"),
        "study_pipeline": metadata.get("study_pipeline"),
        "workspace_template": metadata.get("workspace_template"),
        "training_preset": metadata.get("training_preset"),
        "training_preset_override": metadata.get("training_preset_override"),
        "runs": int(result.runs),
        "seed_values": ",".join(str(seed) for seed in metadata.get("seed_values", ())),
        "best_seed": metadata.get("best_seed"),
        "export_dir": metadata.get("export_dir"),
    }
    row.update(_flatten_metric_summaries(dict(result.train_metrics), "train"))
    row.update(_flatten_metric_summaries(dict(result.test_metrics), "test"))
    row.update(_flatten_metric_summaries(dict(result.structural_metrics), "structure"))
    row.update(_flatten_metric_summaries(dict(result.explainability_metrics), "explainability"))
    for key, value in dict(result.stability_metrics).items():
        row[f"stability_{key}"] = float(value)
    return row


def _seed_row_from_entry(*, seed: int, entry: BenchmarkEntryResult) -> dict[str, Any]:
    row = {
        "seed": seed,
        "model_name": entry.model_name,
        "model_label": _display_model_name(entry.model_name),
        "family": entry.family,
        "article_role": "external_baseline" if entry.family == "sklearn" else entry.family,
        "variant_name": None,
        "variant_label": None,
        "study_pipeline": None,
        "workspace_template": None,
        "training_preset": None,
        "training_preset_override": None,
        "epochs_ran": None,
        "export_dir": None,
    }
    row.update(_flatten_metric_block(dict(entry.train_metrics), "train"))
    row.update(_flatten_metric_block(dict(entry.test_metrics), "test"))
    row.update(_flatten_metric_block(dict(entry.structural_metrics), "structure"))
    row.update(_flatten_metric_block(dict(entry.explainability_metrics), "explainability"))
    return row


def _baseline_model_names(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        if row.get("family") != "sklearn":
            continue
        label = str(row.get("model_label") or row.get("model_name"))
        if label not in names:
            names.append(label)
    return names


def _benchmark_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Article Benchmark Report",
        "",
        f"- generated_at_utc: {summary['generated_at_utc']}",
        f"- source_project: {summary['source_project']['name']}",
        f"- task_type: {summary['source_project']['task_type']}",
        f"- target_name: {summary['source_project']['target_name']}",
        f"- benchmark_dir: {summary['benchmark_dir']}",
        f"- seed_count: {summary.get('seed_count', 1)}",
        f"- seeds: {summary.get('seeds', [])}",
        "",
        "## RuFLEX Variants",
    ]
    for item in summary["variant_plan"]:
        lines.append(
            f"- {item['label']} (`{item['name']}`; template=`{item['workspace_template']}`; preset=`{item['training_preset']}`): {item['description']}"
        )

    baseline_models = summary.get("baseline_models") or []
    if baseline_models:
        lines.extend(["", "## External Baselines", ""])
        lines.extend(f"- {name}" for name in baseline_models)

    results = summary["results"]
    if results:
        lines.extend(
            [
                "",
                "## Aggregated Results",
                "",
                _markdown_table(
                    headers=_report_headers(results),
                    rows=[
                        {header: row.get(header) for header in _report_headers(results)}
                        for row in results
                    ],
                ),
            ]
        )
        winners = _winner_lines(summary["source_project"]["task_type"], results)
        if winners:
            lines.extend(["", "## Suggested Winners", ""] + winners)
    return "\n".join(lines)


def _report_headers(results: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "model_name",
        "model_label",
        "family",
        "article_role",
        "variant_name",
        "workspace_template",
        "training_preset",
        "runs",
        "best_seed",
        "test_rmse_mean",
        "test_rmse_std",
        "test_mae_mean",
        "test_mae_std",
        "test_r2_mean",
        "test_r2_std",
        "test_accuracy_mean",
        "test_accuracy_std",
        "test_precision_mean",
        "test_precision_std",
        "test_recall_mean",
        "test_recall_std",
        "test_f1_mean",
        "test_f1_std",
        "export_dir",
    ]
    all_headers: list[str] = []
    for row in results:
        for key in row:
            if key not in all_headers:
                all_headers.append(key)
    ordered = [key for key in preferred if key in all_headers]
    ordered.extend(key for key in all_headers if key not in ordered)
    return ordered


def _markdown_table(headers: list[str], rows: list[dict[str, Any]]) -> str:
    if not headers:
        return "_No rows._"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(header)) for header in headers) + " |")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _winner_lines(task_type: str, results: list[dict[str, Any]]) -> list[str]:
    if task_type == "regression":
        return _winner_lines_for_metrics(results, (("test_rmse", False), ("test_mae", False), ("test_r2", True)))
    return _winner_lines_for_metrics(results, (("test_accuracy", True), ("test_f1", True), ("test_recall", True)))


def _winner_lines_for_metrics(
    results: list[dict[str, Any]],
    metrics: tuple[tuple[str, bool], ...],
) -> list[str]:
    lines = []
    for metric_name, higher_is_better in metrics:
        available = [row for row in results if _metric_value(row, metric_name) is not None]
        if not available:
            continue
        winner = sorted(
            available,
            key=lambda row: float(_metric_value(row, metric_name) or 0.0),
            reverse=higher_is_better,
        )[0]
        value = float(_metric_value(winner, metric_name) or 0.0)
        lines.append(
            f"- {metric_name}: `{winner['model_label']}` ({value:.6f})"
        )
    return lines


def _metric_value(row: dict[str, Any], metric_name: str) -> float | None:
    if row.get(metric_name) is not None:
        return float(row[metric_name])
    mean_key = f"{metric_name}_mean"
    if row.get(mean_key) is not None:
        return float(row[mean_key])
    return None


def _article_materials_summary(summary: dict[str, Any]) -> str:
    results = list(summary.get("results", ()))
    lines = [
        "# Article Materials Summary",
        "",
        f"- source_project: {summary.get('source_project', {}).get('name')}",
        f"- task_type: {summary.get('source_project', {}).get('task_type')}",
        f"- target_name: {summary.get('source_project', {}).get('target_name')}",
        f"- benchmark_dir: {summary.get('benchmark_dir')}",
        f"- generated_at_utc: {summary.get('generated_at_utc')}",
        f"- seed_count: {summary.get('seed_count', 1)}",
        f"- seeds: {summary.get('seeds', [])}",
        "",
        "## Suggested Winners",
        "",
    ]
    winners = _winner_lines(summary.get("source_project", {}).get("task_type", "regression"), results)
    if winners:
        lines.extend(winners)
    else:
        lines.append("- No comparable metric winners were detected.")
    lines.extend(
        [
            "",
            "## Suggested Article Assets",
            "",
            "- use `results_table.csv` for the aggregated mean ± std comparison table;",
            "- use `per_seed_results_table.csv` for the raw per-seed appendix or rebuttal notes;",
            "- use `artifact_index.json` to locate the best RuFLEX exported run folders;",
            "- use `benchmark_report.md` for narrative experiment notes.",
        ]
    )
    return "\n".join(lines)


def _plot_article_results(summary: dict[str, Any], output_dir: Path) -> Path | None:
    results = list(summary.get("results", ()))
    if not results:
        return None

    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    task_type = str(summary.get("source_project", {}).get("task_type", "regression"))
    if task_type == "regression":
        metrics = (("test_rmse", "RMSE на тесте"), ("test_r2", "R2 на тесте"))
    else:
        metrics = (("test_accuracy", "Точность на тесте"), ("test_f1", "F1 на тесте"))

    labels = [_ru_variant_label(str(row.get("model_label") or row.get("model_name"))) for row in results]
    figure, axes = plt.subplots(1, len(metrics), figsize=(7.4 * len(metrics), 5.8))
    if len(metrics) == 1:
        axes = [axes]

    for axis, (metric_key, metric_title) in zip(axes, metrics, strict=False):
        mean_key = f"{metric_key}_mean"
        std_key = f"{metric_key}_std"
        values = [row.get(mean_key) for row in results]
        errors = [row.get(std_key) for row in results]
        positions = np.arange(len(labels))
        axis.bar(
            positions,
            [0.0 if value is None else float(value) for value in values],
            yerr=[0.0 if error is None else float(error) for error in errors],
            capsize=4,
            color="#4C78A8",
            alpha=0.92,
        )
        axis.set_title(metric_title, fontsize=16)
        axis.set_xticks(list(positions))
        axis.set_xticklabels(labels, rotation=24, ha="right", fontsize=10)
        axis.tick_params(axis="y", labelsize=11)
        axis.grid(axis="y", alpha=0.25)
        for position, value in enumerate(values):
            if value is None:
                continue
            axis.text(position, float(value), f"{float(value):.4f}", ha="center", va="bottom", fontsize=9)

    figure.tight_layout()
    path = output_dir / "results_overview.png"
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    return path


def _render_best_run_assets(summary: dict[str, Any], output_dir: Path) -> dict[str, str]:
    best_row = _best_result_row(summary)
    if best_row is None or best_row.get("export_dir") is None:
        return {}

    try:
        import matplotlib.pyplot as plt
    except Exception:
        return {}

    export_dir = Path(str(best_row["export_dir"])).expanduser().resolve()
    project = Project.load_project_from_exported_study(export_dir)
    files: dict[str, str] = {}

    if project.training_summary is not None:
        history_figure = plot_training_history(project.training_summary)
        history_path = output_dir / "best_training_history.png"
        history_figure.savefig(history_path, dpi=200, bbox_inches="tight")
        plt.close(history_figure)
        files["best_training_history"] = str(history_path)

    for variable in project.variables[: min(3, len(project.variables))]:
        if variable.value_range is None:
            continue
        figure = plot_membership_functions(variable)
        variable_path = output_dir / f"membership_{_slug(variable.name)}.png"
        figure.savefig(variable_path, dpi=200, bbox_inches="tight")
        plt.close(figure)
        files[f"membership_{variable.name}"] = str(variable_path)

    if project.dataset is None:
        return files

    sample_frame = project.dataset.frame.loc[:, list(project.feature_names)].iloc[[0]]
    dashboard = project.dashboard(sample_frame, top_k_rules=3)[0]

    decision_rules_path = _plot_named_values(
        labels=[entry.rule_name for entry in dashboard.top_decision_rules],
        values=[_first_value(entry.contribution) for entry in dashboard.top_decision_rules],
        title="Вклад наиболее активных правил",
        ylabel="Вклад",
        path=output_dir / "best_sample_top_rules.png",
    )
    if decision_rules_path is not None:
        files["best_sample_top_rules"] = str(decision_rules_path)

    hidden_concepts_path = _plot_named_values(
        labels=[entry.concept_name for entry in dashboard.hidden_concepts],
        values=[entry.value for entry in dashboard.hidden_concepts],
        title="Скрытые нечеткие концепты",
        ylabel="Значение",
        path=output_dir / "best_sample_hidden_concepts.png",
    )
    if hidden_concepts_path is not None:
        files["best_sample_hidden_concepts"] = str(hidden_concepts_path)

    decision_concepts_path = _plot_named_values(
        labels=[entry.concept_name for entry in dashboard.decision_concept_contributions],
        values=[_first_value(entry.contribution) for entry in dashboard.decision_concept_contributions],
        title="Вклад решающих концептов",
        ylabel="Вклад",
        path=output_dir / "best_sample_decision_concepts.png",
    )
    if decision_concepts_path is not None:
        files["best_sample_decision_concepts"] = str(decision_concepts_path)

    fuzzification_path = _plot_sample_fuzzification(dashboard, output_dir / "best_sample_fuzzification.png")
    if fuzzification_path is not None:
        files["best_sample_fuzzification"] = str(fuzzification_path)

    concept_flow_path = output_dir / "best_sample_concept_flow.txt"
    concept_flow_path.write_text(project.concept_flow(sample_frame, top_k_rules=3, as_text=True), encoding="utf-8")
    files["best_sample_concept_flow"] = str(concept_flow_path)

    rule_chain_path = output_dir / "best_sample_rule_chain.txt"
    rule_chain_path.write_text(project.rule_chain_flow(sample_frame, top_k_rules=3, as_text=True), encoding="utf-8")
    files["best_sample_rule_chain"] = str(rule_chain_path)
    return files


def _best_result_row(summary: dict[str, Any]) -> dict[str, Any] | None:
    results = [row for row in summary.get("results", ()) if row.get("export_dir") is not None]
    if not results:
        return None
    task_type = str(summary.get("source_project", {}).get("task_type", "regression"))
    if task_type == "regression":
        comparable = [row for row in results if row.get("test_rmse_mean") is not None]
        if comparable:
            return sorted(comparable, key=lambda row: float(row["test_rmse_mean"]))[0]
        comparable = [row for row in results if row.get("test_r2_mean") is not None]
        if comparable:
            return sorted(comparable, key=lambda row: float(row["test_r2_mean"]), reverse=True)[0]
        return None
    comparable = [row for row in results if row.get("test_f1_mean") is not None]
    if comparable:
        return sorted(comparable, key=lambda row: float(row["test_f1_mean"]), reverse=True)[0]
    comparable = [row for row in results if row.get("test_accuracy_mean") is not None]
    if comparable:
        return sorted(comparable, key=lambda row: float(row["test_accuracy_mean"]), reverse=True)[0]
    return None


def _best_seed_row(task_type: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    if task_type == "regression":
        comparable = [row for row in rows if row.get("test_rmse") is not None]
        if comparable:
            return sorted(comparable, key=lambda row: float(row["test_rmse"]))[0]
        comparable = [row for row in rows if row.get("test_r2") is not None]
        if comparable:
            return sorted(comparable, key=lambda row: float(row["test_r2"]), reverse=True)[0]
        return None
    comparable = [row for row in rows if row.get("test_f1") is not None]
    if comparable:
        return sorted(comparable, key=lambda row: float(row["test_f1"]), reverse=True)[0]
    comparable = [row for row in rows if row.get("test_accuracy") is not None]
    if comparable:
        return sorted(comparable, key=lambda row: float(row["test_accuracy"]), reverse=True)[0]
    return None


def _display_model_name(model_name: str) -> str:
    mapping = {
        "linear_regression": "Linear Regression",
        "logistic_regression": "Logistic Regression",
        "hist_gradient_boosting_regressor": "Gradient Boosting",
        "hist_gradient_boosting_classifier": "Gradient Boosting",
        "random_forest_regressor": "Random Forest",
        "random_forest_classifier": "Random Forest",
        "mlp_regressor": "MLP",
        "mlp_classifier": "MLP",
        "xgboost_regressor": "XGBoost",
        "xgboost_classifier": "XGBoost",
        "catboost_regressor": "CatBoost",
        "catboost_classifier": "CatBoost",
        "flat_baseline": "Flat Baseline",
        "flat_interpretable": "Flat Interpretable",
        "deep_stage1_ablation": "Deep Depth 1",
        "deep_article_demo": "Sequential Deep Reference",
        "deep_dual_path": "Deep Dual Path",
        "deep_dual_raw_final": "Deep Dual Shortcut",
        "deep_dual_path_block3": "Deep Dual Context",
    }
    return mapping.get(model_name, model_name.replace("_", " ").title())


def _plot_named_values(
    *,
    labels: list[str],
    values: list[float],
    title: str,
    ylabel: str,
    path: Path,
) -> Path | None:
    filtered = [(label, float(value)) for label, value in zip(labels, values, strict=False) if value is not None]
    if not filtered:
        return None

    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(9, 5))
    positions = np.arange(len(filtered))
    plot_labels = [item[0] for item in filtered]
    plot_values = [item[1] for item in filtered]
    axis.bar(positions, plot_values, color="#4C78A8")
    axis.set_title(title, fontsize=16)
    axis.set_ylabel(ylabel, fontsize=13)
    axis.set_xticks(positions)
    axis.set_xticklabels(plot_labels, rotation=18, ha="right", fontsize=11)
    axis.tick_params(axis="y", labelsize=11)
    axis.grid(axis="y", alpha=0.25)
    for position, value in enumerate(plot_values):
        axis.text(position, value, f"{value:.4f}", ha="center", va="bottom", fontsize=10)
    figure.tight_layout()
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    return path


def _plot_sample_fuzzification(dashboard: Any, path: Path) -> Path | None:
    blocks = list(dashboard.hidden_blocks)
    if not blocks:
        blocks = [dashboard.decision_block]
    if not blocks:
        return None
    fuzzification = list(blocks[0].variable_fuzzification)
    if not fuzzification:
        return None

    import matplotlib.pyplot as plt

    labels = [entry.variable_name for entry in fuzzification]
    term_names = [membership.term_name for membership in fuzzification[0].memberships]
    matrix = np.asarray(
        [
            [membership.membership for membership in entry.memberships]
            for entry in fuzzification
        ],
        dtype=float,
    )

    figure, axis = plt.subplots(figsize=(8.5, 5.2))
    image = axis.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0.0, vmax=1.0)
    axis.set_title("Карта фаззификации объекта", fontsize=16)
    axis.set_xlabel("Терм", fontsize=13)
    axis.set_ylabel("Переменная", fontsize=13)
    axis.set_xticks(np.arange(len(term_names)))
    axis.set_xticklabels(term_names, rotation=18, ha="right", fontsize=11)
    axis.set_yticks(np.arange(len(labels)))
    axis.set_yticklabels(labels, fontsize=11)
    figure.colorbar(image, ax=axis, shrink=0.85)
    figure.tight_layout()
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    return path


def _first_value(values: tuple[float, ...]) -> float:
    return float(values[0]) if values else 0.0


def _ru_variant_label(label: str) -> str:
    mapping = {
        "Flat Baseline": "Плоская базовая",
        "Flat Interpretable": "Плоская интерпретируемая",
        "Deep Depth 1": "Глубокая глубина 1",
        "Deep Article Demo": "Глубокий демонстрационный",
        "Deep No Regularization": "Глубокий без регуляризации",
        "Deep Research": "Глубокий расширенный",
        "Linear Regression": "Линейная регрессия",
        "Logistic Regression": "Логистическая регрессия",
        "Gradient Boosting": "Градиентный бустинг",
        "Random Forest": "Случайный лес",
        "MLP": "Многослойный персептрон",
        "XGBoost": "XGBoost",
        "CatBoost": "CatBoost",
    }
    return mapping.get(label, label)
