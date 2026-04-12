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
        "--list",
        action="store_true",
        help="Print available dataset recipes and exit.",
    )
    args = parser.parse_args()

    if args.list:
        for item in list_article_dataset_recipes():
            print(f"- {item['name']}: {item['label']} [{item['task_type']}]")
        return

    manifests = prepare_article_datasets(args.datasets, output_root=args.output_root)
    for manifest in manifests:
        print(manifest["output_dir"])


if __name__ == "__main__":
    main()
