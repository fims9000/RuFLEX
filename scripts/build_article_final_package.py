from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from check_article_readiness import build_readiness_report
from build_article_illustrated_manuscripts import build_illustrated_manuscripts
from build_article_submission_bundle import build_submission_bundle
from build_article_figure_boards import build_figure_board
from render_article_profile_docs import render_article_profile_docs

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the full RuFLEX article package.")
    parser.add_argument(
        "--skip-suite",
        action="store_true",
        help="Reuse the latest existing article suite instead of running a new one.",
    )
    args = parser.parse_args()

    if not args.skip_suite:
        _run_python_script(ROOT / "scripts/run_article_suite.py")

    suite_dir = _latest_suite_dir(ROOT / "experiments/article_suite")
    suite_summary = _load_suite_summary(suite_dir)
    render_article_profile_docs()

    for item in suite_summary.get("dataset_runs", ()):
        materials_dir = Path(str(item["materials_dir"]))
        task_type = str((item.get("dataset") or {}).get("task_type"))
        if task_type == "regression":
            build_figure_board(
                asset_dir=materials_dir,
                title="RuFLEX Regression Explainability Board",
                output_path=materials_dir / "article_board_regression.png",
            )
        elif task_type == "binary_classification":
            build_figure_board(
                asset_dir=materials_dir,
                title="RuFLEX Classification Explainability Board",
                output_path=materials_dir / "article_board_classification.png",
            )

    _convert_with_libreoffice(ROOT / "docs/article/paper_draft.md", ROOT / "docs/article")
    _convert_with_libreoffice(ROOT / "docs/article/shablon_dokladov_ready.md", ROOT / "docs/article")
    _convert_with_libreoffice(ROOT / "docs/article/conference_template_ready_en.md", ROOT / "docs/article")
    _convert_with_libreoffice(ROOT / "docs/article/rinc_draft.txt", ROOT / "docs/article")
    build_illustrated_manuscripts()
    build_submission_bundle(suite_dir=suite_dir)
    build_readiness_report(suite_dir=suite_dir, run_tests=False)
    bundle_dir = build_submission_bundle(suite_dir=suite_dir)
    print(bundle_dir)


def _run_python_script(path: Path) -> None:
    subprocess.run([sys.executable, str(path)], check=True, cwd=ROOT)


def _convert_with_libreoffice(source: Path, output_dir: Path) -> None:
    subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            str(output_dir),
            str(source),
        ],
        check=True,
        cwd=ROOT,
    )


def _latest_suite_dir(root_dir: Path) -> Path:
    candidates = sorted((path for path in root_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
    if not candidates:
        raise FileNotFoundError(f"No article suites were found under: {root_dir}")
    return candidates[-1]


def _load_suite_summary(suite_dir: Path) -> dict:
    import json

    return json.loads((suite_dir / "article_suite_summary.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
