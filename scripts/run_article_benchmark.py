from __future__ import annotations

import argparse
from pathlib import Path

from ruflex import Project, article_benchmark_plan, run_article_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an article-oriented RuFLEX benchmark suite.")
    parser.add_argument("--csv", required=True, help="Path to the source CSV dataset.")
    parser.add_argument("--target", required=True, help="Target column name.")
    parser.add_argument("--task-type", default="regression", help="Task type: regression or binary_classification.")
    parser.add_argument("--output-root", default="experiments/article_benchmark", help="Where to store benchmark outputs.")
    parser.add_argument(
        "--variants",
        nargs="*",
        default=None,
        help="Optional variant names from article_benchmark_plan().",
    )
    parser.add_argument(
        "--training-preset-override",
        default=None,
        help="Optional preset override such as fast_debug for quick benchmark smoke runs.",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    project = Project(name=Path(args.csv).stem, task_type=args.task_type)
    project.from_csv(
        args.csv,
        target_column=args.target,
        validation_fraction=args.validation_fraction,
        test_fraction=args.test_fraction,
    )

    print("Article benchmark plan:")
    for item in article_benchmark_plan(project):
        print(f"- {item['name']}: {item['study_pipeline']} ({item['description']})")

    summary = run_article_benchmark(
        project,
        output_root=args.output_root,
        variant_names=args.variants,
        training_preset_override=args.training_preset_override,
    )
    print(summary["benchmark_dir"])


if __name__ == "__main__":
    main()
