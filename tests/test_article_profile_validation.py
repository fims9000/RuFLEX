from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from article_profile import analyze_article_profile  # noqa: E402


def test_profile_analysis_detects_template_placeholders() -> None:
    payload = json.loads((ROOT / "docs/article/article_profile.template.json").read_text(encoding="utf-8"))
    report = analyze_article_profile(payload)

    assert report["status"] == "template_placeholders_detected"
    assert not report["errors"]
    assert any("placeholder email" in item for item in report["placeholder_warnings"])
    assert any("placeholder ORCID" in item for item in report["placeholder_warnings"])


def test_profile_analysis_accepts_realistic_author_payload() -> None:
    payload = {
        "title_ru": "RuFLEX",
        "title_en": "RuFLEX",
        "authors": [
            {
                "name_ru": "Иван Иванов",
                "name_en": "Ivan Ivanov",
                "email": "ivan.ivanov@example.org",
                "orcid": "0000-0001-2345-6789",
                "affiliation_ru": "Университет, Москва, Россия",
                "affiliation_en": "University, Moscow, Russia",
            }
        ],
        "keywords_ru": ["глубокое нечеткое обучение"],
        "keywords_en": ["deep fuzzy learning"],
        "funding_ru": "Нет.",
        "funding_en": "None.",
        "acknowledgment_ru": "Спасибо коллегам.",
        "acknowledgment_en": "Thanks to colleagues.",
    }

    report = analyze_article_profile(payload)

    assert report["status"] == "ready"
    assert not report["errors"]
    assert not report["warnings"]
    assert not report["placeholder_warnings"]


def test_profile_analysis_rejects_empty_or_invalid_author_fields() -> None:
    payload = {
        "title_ru": "RuFLEX",
        "title_en": "RuFLEX",
        "authors": [
            {
                "name_ru": "",
                "name_en": "Ivan Ivanov",
                "email": "broken-email",
                "orcid": "broken-orcid",
                "affiliation_ru": "",
                "affiliation_en": "University, Moscow, Russia",
            }
        ],
        "keywords_ru": ["глубокое нечеткое обучение"],
        "keywords_en": ["deep fuzzy learning"],
        "funding_ru": "Нет.",
        "funding_en": "None.",
        "acknowledgment_ru": "Спасибо коллегам.",
        "acknowledgment_en": "Thanks to colleagues.",
    }

    report = analyze_article_profile(payload)

    assert report["status"] == "invalid"
    assert any("empty Russian author name" in item for item in report["errors"])
    assert any("invalid email" in item for item in report["errors"])
    assert any("invalid ORCID" in item for item in report["errors"])
