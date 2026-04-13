from __future__ import annotations

import argparse
from pathlib import Path

from build_article_q2_package import (
    EXT_DOC_DOCX,
    MAIN_DOC_DOCX,
    PACKAGE_DIR,
    PACKAGE_ZIP,
    build_q2_article_package,
)
from check_article_readiness import build_readiness_report


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the current RuFLEX article package via the Q2 submission pipeline."
    )
    parser.add_argument(
        "--skip-suite",
        action="store_true",
        help="Compatibility flag from the legacy article flow. It is accepted but no longer changes the Q2 build.",
    )
    args = parser.parse_args()

    if args.skip_suite:
        print("build_article_final_package.py: `--skip-suite` is kept only for compatibility with the legacy flow.")

    build_q2_article_package()
    build_readiness_report(run_tests=False)
    print(MAIN_DOC_DOCX)
    print(EXT_DOC_DOCX)
    print(PACKAGE_DIR)
    print(PACKAGE_ZIP)


if __name__ == "__main__":
    main()
