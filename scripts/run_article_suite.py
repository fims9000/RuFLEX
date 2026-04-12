from __future__ import annotations

import argparse

from ruflex.experiments.article_suite import run_article_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full RuFLEX article dataset -> benchmark -> materials suite.")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="Optional dataset recipe names. If omitted, the full default article suite is executed.",
    )
    parser.add_argument("--dataset-root", default="experiments/datasets")
    parser.add_argument("--benchmark-root", default="experiments/article_benchmark")
    parser.add_argument("--assets-root", default="docs/article/assets")
    parser.add_argument("--suite-root", default="experiments/article_suite")
    parser.add_argument("--training-preset-override", default=None)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    summary = run_article_suite(
        dataset_names=args.datasets,
        dataset_root=args.dataset_root,
        benchmark_root=args.benchmark_root,
        assets_root=args.assets_root,
        suite_root=args.suite_root,
        training_preset_override=args.training_preset_override,
        validation_fraction=args.validation_fraction,
        test_fraction=args.test_fraction,
    )
    print(summary["suite_dir"])


if __name__ == "__main__":
    main()
