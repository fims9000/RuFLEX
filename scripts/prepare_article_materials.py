from __future__ import annotations

import argparse

from ruflex import prepare_article_materials


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare article-ready tables and summaries from a benchmark run.")
    parser.add_argument("--benchmark-dir", required=True, help="Path to one saved benchmark directory.")
    parser.add_argument(
        "--output-root",
        default="docs/article/assets",
        help="Root directory where article-ready materials should be written.",
    )
    args = parser.parse_args()

    payload = prepare_article_materials(args.benchmark_dir, output_root=args.output_root)
    print(payload["output_dir"])


if __name__ == "__main__":
    main()
