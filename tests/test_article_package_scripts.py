from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def article_repo(tmp_path: Path) -> Iterator[tuple[Path, dict[str, str]]]:
    """Run destructive document generators only on independent fixture copies."""
    def source_hashes() -> dict[str, str]:
        return {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "docs/article").rglob("*") if path.is_file()
        }

    before = source_hashes()
    root = tmp_path / "article-repo"
    shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "docs/article", root / "docs/article")
    env = os.environ.copy()
    office = shutil.which("libreoffice")
    if office and os.name == "posix":
        # Never attach conversion jobs to the user's interactive Office profile.
        bin_dir = root / "test-bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "libreoffice"
        profile = (root / "office-profile").as_uri()
        wrapper.write_text(
            f"#!/bin/sh\nexec {shlex.quote(office)} "
            f"{shlex.quote('-env:UserInstallation=' + profile)} \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    yield root, env
    assert source_hashes() == before, "Document tests must not modify checkout articles"


def test_build_article_final_package_builds_q2_outputs(article_repo) -> None:
    root, env = article_repo
    result = subprocess.run(
        [sys.executable, "scripts/build_article_final_package.py", "--skip-suite"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    assert (root / "docs/article/article_final_ru.docx").exists()
    assert (root / "docs/article/article_extended_materials_ru.docx").exists()
    assert (root / "docs/article/q2_submission_package").exists()
    assert (root / "docs/article/q2_submission_package.zip").exists()


def test_check_article_readiness_reports_current_q2_state(article_repo) -> None:
    root, env = article_repo
    build_result = subprocess.run(
        [sys.executable, "scripts/build_article_final_package.py", "--skip-suite"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_result.returncode == 0, build_result.stderr or build_result.stdout

    result = subprocess.run(
        [sys.executable, "scripts/check_article_readiness.py"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    report_path = Path(result.stdout.strip().splitlines()[-1])
    assert report_path.exists()

    json_path = root / "docs/article/readiness_report.json"
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

    packaged_report = root / "docs/article/q2_submission_package/docs/readiness_report.md"
    assert packaged_report.exists()


def test_strict_submission_gate_fails_while_author_metadata_is_incomplete(article_repo) -> None:
    root, env = article_repo
    result = subprocess.run(
        [sys.executable, "scripts/check_article_readiness.py", "--strict-submission"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "strict-submission gate failed" in (result.stderr or result.stdout)
