from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_build_article_final_package_builds_q2_outputs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_article_final_package.py", "--skip-suite"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    assert (ROOT / "docs/article/article_final_ru.docx").exists()
    assert (ROOT / "docs/article/article_extended_materials_ru.docx").exists()
    assert (ROOT / "docs/article/q2_submission_package").exists()
    assert (ROOT / "docs/article/q2_submission_package.zip").exists()


def test_check_article_readiness_reports_current_q2_state() -> None:
    build_result = subprocess.run(
        [sys.executable, "scripts/build_article_final_package.py", "--skip-suite"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_result.returncode == 0, build_result.stderr or build_result.stdout

    result = subprocess.run(
        [sys.executable, "scripts/check_article_readiness.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    report_path = Path(result.stdout.strip().splitlines()[-1])
    assert report_path.exists()

    json_path = ROOT / "docs/article/readiness_report.json"
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["overall_status"] == "pass"
    assert payload["submission_status"] == "pending"
    assert payload["author_metadata_status"] == "incomplete"
    assert any(item["name"] == "q2_package_zip" and item["ok"] for item in payload["checks"])
    assert any(item["name"] == "package_doc:article_final_ru.docx" and item["ok"] for item in payload["checks"])
    assert any(item["name"] == "package_table:california_housing_regression_summary.csv" and item["ok"] for item in payload["checks"])
    assert any(item["name"] == "author_line_present" and item["ok"] for item in payload["checks"])
    assert any(item["name"] == "author_emails_present" and not item["ok"] for item in payload["checks"])

    packaged_report = ROOT / "docs/article/q2_submission_package/docs/readiness_report.md"
    assert packaged_report.exists()


def test_strict_submission_gate_fails_while_author_metadata_is_incomplete() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_article_readiness.py", "--strict-submission"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "strict-submission gate failed" in (result.stderr or result.stdout)
