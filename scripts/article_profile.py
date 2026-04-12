from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "docs/article/article_profile.json"
PROFILE_TEMPLATE_PATH = ROOT / "docs/article/article_profile.template.json"


def load_article_profile() -> dict[str, Any]:
    profile_path = PROFILE_PATH if PROFILE_PATH.exists() else PROFILE_TEMPLATE_PATH
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    _validate_profile(payload)
    return payload


def format_keywords(items: list[str]) -> str:
    return "; ".join(item.strip() for item in items if item.strip())


def format_author_names(profile: dict[str, Any], *, language: str) -> str:
    key = "name_ru" if language == "ru" else "name_en"
    return ", ".join(str(author[key]).strip() for author in profile["authors"])


def format_affiliations(profile: dict[str, Any], *, language: str) -> list[str]:
    key = "affiliation_ru" if language == "ru" else "affiliation_en"
    values: list[str] = []
    for author in profile["authors"]:
        value = str(author[key]).strip()
        if value and value not in values:
            values.append(value)
    return values


def format_emails(profile: dict[str, Any]) -> str:
    values = [str(author["email"]).strip() for author in profile["authors"] if str(author["email"]).strip()]
    return ", ".join(values)


def _validate_profile(payload: dict[str, Any]) -> None:
    required_root = (
        "title_ru",
        "title_en",
        "authors",
        "keywords_ru",
        "keywords_en",
        "funding_ru",
        "funding_en",
        "acknowledgment_ru",
        "acknowledgment_en",
    )
    for key in required_root:
        if key not in payload:
            raise KeyError(f"Article profile is missing required key: {key}")
    authors = payload["authors"]
    if not isinstance(authors, list) or not authors:
        raise ValueError("Article profile must contain at least one author.")
    for index, author in enumerate(authors):
        for key in ("name_ru", "name_en", "email", "affiliation_ru", "affiliation_en"):
            if key not in author:
                raise KeyError(f"Article profile author #{index} is missing required key: {key}")
