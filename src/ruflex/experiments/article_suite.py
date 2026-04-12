from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruflex.experiments.article_benchmark import prepare_article_materials, run_article_benchmark
from ruflex.experiments.article_datasets import prepare_article_datasets
from ruflex.io.project import save_manifest
from ruflex.sdk.project import Project


def run_article_suite(
    *,
    dataset_names: tuple[str, ...] | list[str] | None = None,
    dataset_root: str | Path = "experiments/datasets",
    benchmark_root: str | Path = "experiments/article_benchmark",
    assets_root: str | Path = "docs/article/assets",
    suite_root: str | Path = "experiments/article_suite",
    training_preset_override: str | None = None,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
) -> dict[str, Any]:
    dataset_manifests = prepare_article_datasets(dataset_names, output_root=dataset_root)

    suite_dir = _suite_directory(suite_root)
    suite_dir.mkdir(parents=True, exist_ok=False)

    suite_rows = []
    dataset_runs = []
    for dataset_manifest in dataset_manifests:
        project = Project(
            name=dataset_manifest["name"],
            task_type=dataset_manifest["task_type"],
            description=dataset_manifest["description"],
        )
        project.from_csv(
            dataset_manifest["csv_path"],
            target_column=str(dataset_manifest["target_column"]),
            feature_columns=tuple(dataset_manifest["feature_columns"]),
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
            random_state=int(dataset_manifest.get("random_state", 42)),
        )

        benchmark = run_article_benchmark(
            project,
            output_root=benchmark_root,
            training_preset_override=training_preset_override,
        )
        materials = prepare_article_materials(benchmark["benchmark_dir"], output_root=assets_root)
        best_variant = _best_variant_for_task(
            str(dataset_manifest["task_type"]),
            list(benchmark.get("results", ())),
        )
        dataset_runs.append(
            {
                "dataset": dataset_manifest,
                "benchmark_dir": benchmark["benchmark_dir"],
                "materials_dir": materials["output_dir"],
                "best_variant": best_variant,
                "results": benchmark["results"],
            }
        )
        for row in benchmark["results"]:
            suite_rows.append(
                {
                    "dataset_name": dataset_manifest["name"],
                    "dataset_label": dataset_manifest["label"],
                    "task_type": dataset_manifest["task_type"],
                    "target_column": dataset_manifest["target_column"],
                    **row,
                }
            )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_dir": str(suite_dir),
        "training_preset_override": training_preset_override,
        "dataset_runs": dataset_runs,
        "rows": suite_rows,
    }

    summary_path = suite_dir / "article_suite_summary.json"
    save_manifest(summary, summary_path)
    csv_path = suite_dir / "article_suite_results.csv"
    _write_csv(suite_rows, csv_path)
    markdown_path = suite_dir / "article_suite_results.md"
    markdown_path.write_text(_suite_markdown(summary), encoding="utf-8")
    return {
        "suite_dir": str(suite_dir),
        "summary_path": str(summary_path),
        "results_csv": str(csv_path),
        "results_md": str(markdown_path),
        "dataset_runs": dataset_runs,
        "rows": suite_rows,
    }


def _suite_directory(root_dir: str | Path) -> Path:
    root = Path(root_dir).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).isoformat().replace(":", "-")
    candidate = root / f"{_slug(timestamp)}_article_suite"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        alternative = root / f"{_slug(timestamp)}_article_suite_{index}"
        if not alternative.exists():
            return alternative
        index += 1


def _slug(value: str) -> str:
    slug = "".join(character if character.isalnum() else "_" for character in value.strip().lower())
    slug = slug.strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "artifact"


def _best_variant_for_task(task_type: str, results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    if task_type == "regression":
        comparable = [row for row in results if row.get("test_rmse") is not None]
        if comparable:
            return dict(sorted(comparable, key=lambda row: float(row["test_rmse"]))[0])
        comparable = [row for row in results if row.get("test_r2") is not None]
        if comparable:
            return dict(sorted(comparable, key=lambda row: float(row["test_r2"]), reverse=True)[0])
        return None
    comparable = [row for row in results if row.get("test_f1") is not None]
    if comparable:
        return dict(sorted(comparable, key=lambda row: float(row["test_f1"]), reverse=True)[0])
    comparable = [row for row in results if row.get("test_accuracy") is not None]
    if comparable:
        return dict(sorted(comparable, key=lambda row: float(row["test_accuracy"]), reverse=True)[0])
    return None


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _suite_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Article Suite Summary",
        "",
        f"- generated_at_utc: {summary['generated_at_utc']}",
        f"- suite_dir: {summary['suite_dir']}",
        f"- training_preset_override: {summary.get('training_preset_override')}",
        "",
        "## Dataset Runs",
        "",
    ]
    for item in summary["dataset_runs"]:
        dataset = item["dataset"]
        lines.append(f"- {dataset['label']} (`{dataset['name']}`)")
        lines.append(f"  benchmark_dir: `{item['benchmark_dir']}`")
        lines.append(f"  materials_dir: `{item['materials_dir']}`")
        if item["best_variant"] is not None:
            best = item["best_variant"]
            lines.append(
                f"  best_variant: `{best.get('variant_label')}` via `{best.get('study_pipeline')}`"
            )
    return "\n".join(lines)
