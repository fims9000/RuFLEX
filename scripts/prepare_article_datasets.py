from __future__ import annotations

import argparse

from ruflex.experiments.article_datasets import list_article_dataset_recipes, prepare_article_datasets


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare reproducible article datasets for RuFLEX benchmarks.")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="Optional recipe names. If omitted, all default article datasets are prepared.",
    )
    parser.add_argument(
        "--output-root",
        default="experiments/datasets",
        help="Root directory where dataset folders should be written.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Optional sample size override applied to each selected dataset recipe.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=None,
        help="Optional random state override applied to each selected dataset recipe.",
    )
    parser.add_argument(
        "--output-name-suffix",
        default=None,
        help="Optional suffix appended to enlarged dataset directory names so canonical datasets are not overwritten.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print available dataset recipes and exit.",
    )
    args = parser.parse_args()

    if args.list:
        for item in list_article_dataset_recipes():
            print(f"- {item['name']}: {item['label']} [{item['task_type']}]")
        return

    manifests = prepare_article_datasets(
        args.datasets,
        output_root=args.output_root,
        sample_size_override=args.sample_size,
        random_state_override=args.random_state,
        output_name_suffix=args.output_name_suffix,
    )
    for manifest in manifests:
        print(manifest["output_dir"])


if __name__ == "__main__":
    main()
