from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ruflex.io.project import load_manifest, save_manifest
from ruflex.sdk.project import Project
from ruflex.visualization.plots import plot_membership_functions, plot_training_history


@dataclass(frozen=True)
class ArticleBenchmarkVariant:
    name: str
    label: str
    study_pipeline: str
    article_role: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "study_pipeline": self.study_pipeline,
            "article_role": self.article_role,
            "description": self.description,
        }


def article_benchmark_plan(project: Project) -> tuple[dict[str, Any], ...]:
    _require_project_dataset(project)
    feature_count = len(project.dataset_config.feature_columns or project.dataset.numeric_feature_columns(project.dataset_config.target_column))

    variants = [
        ArticleBenchmarkVariant(
            name="flat_baseline",
            label="Flat Baseline",
            study_pipeline="flat_baseline_benchmark",
            article_role="baseline",
            description="Reference flat neuro-fuzzy baseline for the article tables.",
        ),
        ArticleBenchmarkVariant(
            name="flat_interpretable",
            label="Flat Interpretable",
            study_pipeline="interpretable_flat_study",
            article_role="interpretable_baseline",
            description="Compact interpretable flat model for rule-oriented comparison.",
        ),
        ArticleBenchmarkVariant(
            name="deep_article_demo",
            label="Deep Article Demo",
            study_pipeline="deep_article_demo",
            article_role="primary_deep_model",
            description="Primary deep fuzzy feature learning configuration for the paper.",
        ),
    ]
    if feature_count >= 4:
        variants.append(
            ArticleBenchmarkVariant(
                name="deep_research",
                label="Deep Research",
                study_pipeline="deep_research_study",
                article_role="extended_deep_model",
                description="Broader deep fuzzy configuration for extended article comparisons.",
            )
        )
    return tuple(item.to_dict() for item in variants)


def run_article_benchmark(
    project: Project,
    *,
    output_root: str | Path = "experiments/article_benchmark",
    variant_names: tuple[str, ...] | list[str] | None = None,
    training_preset_override: str | None = None,
) -> dict[str, Any]:
    _require_project_dataset(project)

    benchmark_dir = _benchmark_directory(output_root=output_root, project_name=project.name)
    benchmark_dir.mkdir(parents=True, exist_ok=False)
    runs_root = benchmark_dir / "runs"
    runs_root.mkdir(exist_ok=True)

    plan = article_benchmark_plan(project)
    selected_plan = _select_variants(plan, variant_names)
    results = []
    for variant in selected_plan:
        benchmark_project = _clone_project_for_benchmark(project, variant_name=str(variant["name"]))
        study_record = benchmark_project.run_study_pipeline(
            str(variant["study_pipeline"]),
            export_root=runs_root,
            training_preset_override=training_preset_override,
        )
        result_row = {
            "variant_name": variant["name"],
            "variant_label": variant["label"],
            "article_role": variant["article_role"],
            "study_pipeline": variant["study_pipeline"],
            "training_preset": study_record.get("training_preset"),
            "training_preset_override": study_record.get("training_preset_override"),
            "model_kind": benchmark_project.model_kind,
            "epochs_ran": study_record.get("epochs_ran"),
            "training_source": study_record.get("training_source"),
            "export_dir": (
                None
                if study_record.get("artifact_export") is None
                else study_record["artifact_export"].get("export_dir")
            ),
        }
        result_row.update(_flatten_metric_block(study_record.get("train_metrics"), "train"))
        result_row.update(_flatten_metric_block(study_record.get("validation_metrics"), "validation"))
        result_row.update(_flatten_metric_block(study_record.get("test_metrics"), "test"))
        results.append(result_row)

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
        "results": results,
        "training_preset_override": training_preset_override,
    }

    save_manifest(summary, benchmark_dir / "benchmark_results.json")
    save_manifest({"variants": [dict(item) for item in selected_plan]}, benchmark_dir / "benchmark_plan.json")
    _write_results_csv(results, benchmark_dir / "benchmark_results.csv")
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
                "variant_count": len(payload.get("results", ())),
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

    artifact_index_path = output_dir / "artifact_index.json"
    save_manifest(
        {
            "benchmark_dir": str(benchmark_root),
            "artifacts": [
                {
                    "variant_name": row.get("variant_name"),
                    "variant_label": row.get("variant_label"),
                    "study_pipeline": row.get("study_pipeline"),
                    "export_dir": row.get("export_dir"),
                }
                for row in results
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
        "variant_count": len(results),
    }


def _require_project_dataset(project: Project) -> None:
    if project.dataset is None or project.dataset_config is None:
        raise RuntimeError("Attach a dataset before running the article benchmark.")


def _clone_project_for_benchmark(project: Project, *, variant_name: str) -> Project:
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
        random_state=config.random_state,
    )
    return clone


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
    if payload is None:
        return {}
    return {f"{prefix}_{key}": value for key, value in payload.items()}


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


def _benchmark_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Article Benchmark Report",
        "",
        f"- generated_at_utc: {summary['generated_at_utc']}",
        f"- source_project: {summary['source_project']['name']}",
        f"- task_type: {summary['source_project']['task_type']}",
        f"- target_name: {summary['source_project']['target_name']}",
        f"- benchmark_dir: {summary['benchmark_dir']}",
        "",
        "## Variants",
    ]
    for item in summary["variant_plan"]:
        lines.append(
            f"- {item['label']} (`{item['study_pipeline']}`): {item['description']}"
        )

    results = summary["results"]
    if results:
        lines.extend(
            [
                "",
                "## Results",
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
        "variant_name",
        "variant_label",
        "article_role",
        "study_pipeline",
        "training_preset",
        "model_kind",
        "test_rmse",
        "test_mae",
        "test_r2",
        "test_accuracy",
        "test_precision",
        "test_recall",
        "test_f1",
        "epochs_ran",
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
        available = [row for row in results if row.get(metric_name) is not None]
        if not available:
            continue
        winner = sorted(
            available,
            key=lambda row: float(row[metric_name]),
            reverse=higher_is_better,
        )[0]
        lines.append(
            f"- {metric_name}: `{winner['variant_label']}` ({float(winner[metric_name]):.6f})"
        )
    return lines


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
            "- use `results_table.csv` for the main comparison table;",
            "- use `results_table.md` for quick insertion into draft materials;",
            "- use `artifact_index.json` to locate the exported run folders;",
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
        metrics = (("test_rmse", "Test RMSE"), ("test_r2", "Test R2"))
    else:
        metrics = (("test_accuracy", "Test Accuracy"), ("test_f1", "Test F1"))

    labels = [str(row.get("variant_label") or row.get("variant_name")) for row in results]
    figure, axes = plt.subplots(1, len(metrics), figsize=(6 * len(metrics), 4.5))
    if len(metrics) == 1:
        axes = [axes]

    for axis, (metric_key, metric_title) in zip(axes, metrics, strict=False):
        values = [row.get(metric_key) for row in results]
        positions = range(len(labels))
        axis.bar(positions, [0.0 if value is None else float(value) for value in values], color="#4C78A8")
        axis.set_title(metric_title)
        axis.set_xticks(list(positions))
        axis.set_xticklabels(labels, rotation=20, ha="right")
        axis.grid(axis="y", alpha=0.25)
        for position, value in enumerate(values):
            if value is None:
                continue
            axis.text(position, float(value), f"{float(value):.4f}", ha="center", va="bottom", fontsize=8)

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
        title="Top Decision Rule Contributions",
        ylabel="contribution",
        path=output_dir / "best_sample_top_rules.png",
    )
    if decision_rules_path is not None:
        files["best_sample_top_rules"] = str(decision_rules_path)

    hidden_concepts_path = _plot_named_values(
        labels=[entry.concept_name for entry in dashboard.hidden_concepts],
        values=[entry.value for entry in dashboard.hidden_concepts],
        title="Hidden Concepts for Best Sample",
        ylabel="value",
        path=output_dir / "best_sample_hidden_concepts.png",
    )
    if hidden_concepts_path is not None:
        files["best_sample_hidden_concepts"] = str(hidden_concepts_path)

    decision_concepts_path = _plot_named_values(
        labels=[entry.concept_name for entry in dashboard.decision_concept_contributions],
        values=[_first_value(entry.contribution) for entry in dashboard.decision_concept_contributions],
        title="Decision Concept Contributions",
        ylabel="contribution",
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
    results = list(summary.get("results", ()))
    if not results:
        return None
    task_type = str(summary.get("source_project", {}).get("task_type", "regression"))
    if task_type == "regression":
        comparable = [row for row in results if row.get("test_rmse") is not None]
        if comparable:
            return sorted(comparable, key=lambda row: float(row["test_rmse"]))[0]
        comparable = [row for row in results if row.get("test_r2") is not None]
        if comparable:
            return sorted(comparable, key=lambda row: float(row["test_r2"]), reverse=True)[0]
        return None
    comparable = [row for row in results if row.get("test_f1") is not None]
    if comparable:
        return sorted(comparable, key=lambda row: float(row["test_f1"]), reverse=True)[0]
    comparable = [row for row in results if row.get("test_accuracy") is not None]
    if comparable:
        return sorted(comparable, key=lambda row: float(row["test_accuracy"]), reverse=True)[0]
    return None


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

    figure, axis = plt.subplots(figsize=(8, 4.5))
    positions = np.arange(len(filtered))
    plot_labels = [item[0] for item in filtered]
    plot_values = [item[1] for item in filtered]
    axis.bar(positions, plot_values, color="#4C78A8")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.set_xticks(positions)
    axis.set_xticklabels(plot_labels, rotation=20, ha="right")
    axis.grid(axis="y", alpha=0.25)
    for position, value in enumerate(plot_values):
        axis.text(position, value, f"{value:.4f}", ha="center", va="bottom", fontsize=8)
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

    figure, axis = plt.subplots(figsize=(7, 4.5))
    image = axis.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0.0, vmax=1.0)
    axis.set_title("Sample Fuzzification Heatmap")
    axis.set_xlabel("term")
    axis.set_ylabel("variable")
    axis.set_xticks(np.arange(len(term_names)))
    axis.set_xticklabels(term_names, rotation=20, ha="right")
    axis.set_yticks(np.arange(len(labels)))
    axis.set_yticklabels(labels)
    figure.colorbar(image, ax=axis, shrink=0.85)
    figure.tight_layout()
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    return path


def _first_value(values: tuple[float, ...]) -> float:
    return float(values[0]) if values else 0.0
