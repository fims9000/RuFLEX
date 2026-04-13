from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_article_q2_package import (
    BUILD_REPORT_PATH,
    CHECKLIST_PATH,
    DATASETS,
    EXT_DOC_DOCX,
    EXT_DOC_MD,
    EXT_DOC_PDF,
    MAIN_DOC_DOCX,
    MAIN_DOC_MD,
    MAIN_DOC_PDF,
    PACKAGE_DIR,
    PACKAGE_ZIP,
    SCHEMES,
    TABLES_DIR,
    VISUAL_PACKAGE,
    BENCHMARK_SUMMARY,
)


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "docs" / "article"
DEFAULT_REPORT_MD = ARTICLE_DIR / "readiness_report.md"
DEFAULT_REPORT_JSON = ARTICLE_DIR / "readiness_report.json"

EMAIL_PATTERN = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")
ORCID_PATTERN = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")
AFFILIATION_HINTS = (
    "универс",
    "институт",
    "лаборатор",
    "центр",
    "academy",
    "university",
    "institute",
    "laboratory",
    "center",
    "school",
)

REQUIRED_DOCS = (
    MAIN_DOC_MD,
    MAIN_DOC_DOCX,
    MAIN_DOC_PDF,
    EXT_DOC_MD,
    EXT_DOC_DOCX,
    EXT_DOC_PDF,
    VISUAL_PACKAGE,
    BENCHMARK_SUMMARY,
    CHECKLIST_PATH,
    BUILD_REPORT_PATH,
)

Q2_TEST_SUITE = (
    "tests/test_article_dataset_recipes.py",
    "tests/test_toolbox_api.py",
    "tests/test_sdk_smoke.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check readiness of the current RuFLEX Q2 article package.")
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run the stable Q2 article-related smoke suite and include it in the report.",
    )
    parser.add_argument(
        "--strict-submission",
        action="store_true",
        help="Exit with non-zero status unless the package is technically ready and author metadata is complete.",
    )
    args = parser.parse_args()

    report_path = build_readiness_report(run_tests=args.run_tests)
    print(report_path)
    payload = json.loads(DEFAULT_REPORT_JSON.read_text(encoding="utf-8"))
    if args.strict_submission and payload["submission_status"] != "ready":
        print(
            f"strict-submission gate failed: submission_status={payload['submission_status']}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def build_readiness_report(*, run_tests: bool = False) -> Path:
    checks: list[dict[str, Any]] = []
    for path in REQUIRED_DOCS:
        checks.append(
            _check(
                name=f"doc:{path.relative_to(ROOT)}",
                ok=path.exists(),
                detail=str(path),
            )
        )

    checks.append(_check("q2_package_dir", PACKAGE_DIR.exists(), str(PACKAGE_DIR)))
    checks.append(_check("q2_package_zip", PACKAGE_ZIP.exists(), str(PACKAGE_ZIP)))

    for dataset in DATASETS:
        checks.extend(_dataset_checks(dataset))

    checks.extend(_package_checks())

    author_metadata = inspect_author_metadata(MAIN_DOC_MD)
    checks.extend(author_metadata["checks"])

    test_status: dict[str, Any] | None = None
    if run_tests:
        test_status = _run_q2_tests()
        checks.append(
            _check(
                name="pytest_q2_smoke_suite",
                ok=bool(test_status["ok"]),
                detail=test_status["detail"],
            )
        )

    technical_checks = [item for item in checks if not str(item["name"]).startswith("author_")]
    technical_status = "pass" if all(bool(item["ok"]) for item in technical_checks) else "fail"
    submission_status = "ready" if technical_status == "pass" and author_metadata["status"] == "ready" else "pending"

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_kind": "q2_submission_package",
        "overall_status": technical_status,
        "submission_status": submission_status,
        "author_metadata_status": author_metadata["status"],
        "author_metadata_summary": author_metadata["summary"],
        "benchmark_assets": [
            {
                "slug": dataset.slug,
                "asset_dir": str(dataset.asset_dir),
                "results_table": str(dataset.results_table_path),
                "board_path": str(dataset.board_path),
            }
            for dataset in DATASETS
        ],
        "best_results": collect_best_results(),
        "checks": checks,
        "manual_items": [
            {
                "status": "pending",
                "item": "Добавить e-mail авторов в шапку статьи, если этого требует площадка.",
            },
            {
                "status": "pending",
                "item": "Проверить финальную верстку и требования журнала к Word-формулам.",
            },
            {
                "status": "pending",
                "item": "При необходимости дополнить основной текст живыми UI-скриншотами.",
            },
        ],
    }
    if test_status is not None:
        payload["test_status"] = test_status

    DEFAULT_REPORT_MD.write_text(render_markdown(payload), encoding="utf-8")
    DEFAULT_REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    sync_report_into_package()
    return DEFAULT_REPORT_MD


def inspect_author_metadata(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    preamble: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("Аннотация.") or stripped.startswith("## "):
            break
        if stripped:
            preamble.append(stripped)

    authors_present = bool(preamble)
    preamble_text = "\n".join(preamble)
    email_matches = EMAIL_PATTERN.findall(preamble_text)
    orcid_matches = ORCID_PATTERN.findall(preamble_text)
    affiliation_lines = [
        line
        for line in preamble
        if re.match(r"^\d+\s", line)
        or any(token in line.casefold() for token in AFFILIATION_HINTS)
    ]

    checks = [
        _check("author_line_present", authors_present, preamble[0] if preamble else "author line is missing"),
        _check("author_affiliations_present", bool(affiliation_lines), "; ".join(affiliation_lines) or "no affiliations found"),
        _check("author_emails_present", bool(email_matches), ", ".join(email_matches) or "no e-mail addresses found"),
        _check("author_orcids_present", bool(orcid_matches), ", ".join(orcid_matches) or "no ORCID identifiers found"),
    ]

    status = "ready" if all(item["ok"] for item in checks) else "incomplete"
    summary = {
        "authors_line": preamble[0] if preamble else "",
        "affiliations": affiliation_lines,
        "emails": email_matches,
        "orcids": orcid_matches,
    }
    return {"status": status, "summary": summary, "checks": checks}


def collect_best_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for dataset in DATASETS:
        summary_path = TABLES_DIR / f"{dataset.slug}_summary.csv"
        source_path = summary_path if summary_path.exists() else dataset.results_table_path
        if not source_path.exists():
            continue
        rows = list(csv.DictReader(source_path.open(encoding="utf-8")))
        if not rows:
            continue
        if dataset.task_type == "regression":
            best_ruflex = min((row for row in rows if row["class"] == "RuFLEX"), key=lambda row: _metric_mean(row["rmse"]))
            best_external = min(
                (row for row in rows if row["class"] != "RuFLEX"),
                key=lambda row: _metric_mean(row["rmse"]),
            )
            metrics_keys = ("rmse", "mae", "r2")
        else:
            best_ruflex = max(
                (row for row in rows if row["class"] == "RuFLEX"),
                key=lambda row: (_metric_mean(row["accuracy"]), _metric_mean(row["f1"])),
            )
            best_external = max(
                (row for row in rows if row["class"] != "RuFLEX"),
                key=lambda row: (_metric_mean(row["accuracy"]), _metric_mean(row["f1"])),
            )
            metrics_keys = ("accuracy", "f1", "precision", "recall")
        results.append(
            {
                "dataset": dataset.slug,
                "best_ruflex": {"model": best_ruflex["model"], "metrics": {key: best_ruflex[key] for key in metrics_keys}},
                "best_external": {
                    "model": best_external["model"],
                    "metrics": {key: best_external[key] for key in metrics_keys},
                },
            }
        )
    return results


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RuFLEX Q2 readiness report",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- package_kind: `{payload['package_kind']}`",
        f"- overall_status: `{payload['overall_status']}`",
        f"- submission_status: `{payload['submission_status']}`",
        f"- author_metadata_status: `{payload['author_metadata_status']}`",
        "",
        "## Critical automated checks",
        "",
    ]
    for item in payload["checks"]:
        status = "PASS" if item["ok"] else "FAIL"
        lines.append(f"- `{status}` {item['name']}: {item['detail']}")

    lines.extend(["", "## Best benchmark results", ""])
    for item in payload["best_results"]:
        lines.append(
            f"- `{item['dataset']}`: RuFLEX -> {item['best_ruflex']['model']}; external -> {item['best_external']['model']}"
        )

    lines.extend(["", "## Author metadata", ""])
    summary = payload["author_metadata_summary"]
    lines.append(f"- authors_line: `{summary['authors_line']}`")
    lines.append(f"- affiliations: `{', '.join(summary['affiliations']) if summary['affiliations'] else '(missing)'}`")
    lines.append(f"- emails: `{', '.join(summary['emails']) if summary['emails'] else '(missing)'}`")
    lines.append(f"- orcids: `{', '.join(summary['orcids']) if summary['orcids'] else '(missing)'}`")

    if "test_status" in payload:
        lines.extend(
            [
                "",
                "## Q2 smoke tests",
                "",
                f"- status: `{'pass' if payload['test_status']['ok'] else 'fail'}`",
                f"- detail: `{payload['test_status']['detail']}`",
            ]
        )

    lines.extend(["", "## Manual items", ""])
    for item in payload["manual_items"]:
        lines.append(f"- `{item['status']}` {item['item']}")
    return "\n".join(lines)


def _dataset_checks(dataset: Any) -> list[dict[str, Any]]:
    return [
        _check(
            name=f"{dataset.slug}:asset_dir",
            ok=dataset.asset_dir.exists(),
            detail=str(dataset.asset_dir),
        ),
        _check(
            name=f"{dataset.slug}:benchmark_results",
            ok=(dataset.asset_dir / "benchmark_results.json").exists(),
            detail=str(dataset.asset_dir / "benchmark_results.json"),
        ),
        _check(
            name=f"{dataset.slug}:results_table",
            ok=dataset.results_table_path.exists(),
            detail=str(dataset.results_table_path),
        ),
        _check(
            name=f"{dataset.slug}:board",
            ok=dataset.board_path.exists(),
            detail=str(dataset.board_path),
        ),
        _check(
            name=f"{dataset.slug}:overview",
            ok=dataset.overview_path.exists(),
            detail=str(dataset.overview_path),
        ),
    ]


def _package_checks() -> list[dict[str, Any]]:
    package_docs = PACKAGE_DIR / "docs"
    package_figures = PACKAGE_DIR / "figures"
    package_tables = PACKAGE_DIR / "tables"
    checks = [
        _check("package_docs_dir", package_docs.exists(), str(package_docs)),
        _check("package_figures_dir", package_figures.exists(), str(package_figures)),
        _check("package_tables_dir", package_tables.exists(), str(package_tables)),
    ]
    for source in (
        MAIN_DOC_MD,
        EXT_DOC_MD,
        MAIN_DOC_DOCX,
        EXT_DOC_DOCX,
        MAIN_DOC_PDF,
        EXT_DOC_PDF,
        VISUAL_PACKAGE,
        BENCHMARK_SUMMARY,
        CHECKLIST_PATH,
        BUILD_REPORT_PATH,
    ):
        checks.append(
            _check(
                name=f"package_doc:{source.name}",
                ok=(package_docs / source.name).exists(),
                detail=str(package_docs / source.name),
            )
        )
    for figure_path, _caption in SCHEMES:
        checks.append(
            _check(
                name=f"package_figure:{figure_path.name}",
                ok=(package_figures / figure_path.name).exists(),
                detail=str(package_figures / figure_path.name),
            )
        )
    for dataset in DATASETS:
        checks.append(
            _check(
                name=f"package_table:{dataset.slug}_summary.csv",
                ok=(package_tables / f"{dataset.slug}_summary.csv").exists(),
                detail=str(package_tables / f"{dataset.slug}_summary.csv"),
            )
        )
    return checks


def _run_q2_tests() -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", *Q2_TEST_SUITE]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    detail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else (result.stderr.strip() or "no output")
    return {"ok": result.returncode == 0, "detail": detail}


def _metric_mean(value: str) -> float:
    return float(value.split("±", 1)[0].strip())


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def sync_report_into_package() -> None:
    package_docs = PACKAGE_DIR / "docs"
    if not package_docs.exists():
        return
    shutil.copy2(DEFAULT_REPORT_MD, package_docs / DEFAULT_REPORT_MD.name)
    shutil.copy2(DEFAULT_REPORT_JSON, package_docs / DEFAULT_REPORT_JSON.name)


if __name__ == "__main__":
    main()
