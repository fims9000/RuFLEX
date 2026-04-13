from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from article_references import analyze_article_references  # noqa: E402


def test_references_analysis_accepts_current_reference_list() -> None:
    payload = json.loads((ROOT / "docs/article/article_references.json").read_text(encoding="utf-8"))
    report = analyze_article_references(payload)

    assert report["status"] == "ready"
    assert not report["errors"]


def test_references_analysis_rejects_duplicate_or_empty_entries() -> None:
    payload = [
        {"key": "duplicate_ref", "ru": "Test RU", "en": "Test EN"},
        {"key": "duplicate_ref", "ru": "", "en": "Second EN"},
    ]

    report = analyze_article_references(payload)

    assert report["status"] == "invalid"
    assert any("duplicate key" in item for item in report["errors"])
    assert any("empty `ru` entry" in item for item in report["errors"])


def test_references_analysis_marks_placeholder_text_for_review() -> None:
    payload = [
        {
            "key": "todo_ref",
            "ru": "TODO: заполнить русскую ссылку.",
            "en": "TODO: fill in the English reference.",
        }
    ]

    report = analyze_article_references(payload)

    assert report["status"] == "review_needed"
    assert not report["errors"]
    assert report["placeholder_warnings"]
