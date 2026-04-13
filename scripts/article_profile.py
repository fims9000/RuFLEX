from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "docs/article/article_profile.json"
PROFILE_TEMPLATE_PATH = ROOT / "docs/article/article_profile.template.json"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


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


def format_orcids(profile: dict[str, Any]) -> str:
    values = [str(author.get("orcid", "")).strip() for author in profile["authors"] if str(author.get("orcid", "")).strip()]
    return ", ".join(values)


def analyze_article_profile(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    placeholder_warnings: list[str] = []

    authors = payload.get("authors", [])
    seen_emails: set[str] = set()
    seen_orcids: set[str] = set()
    for index, author in enumerate(authors, start=1):
        email = str(author.get("email", "")).strip()
        orcid = str(author.get("orcid", "")).strip()
        name_ru = str(author.get("name_ru", "")).strip()
        name_en = str(author.get("name_en", "")).strip()
        affiliation_ru = str(author.get("affiliation_ru", "")).strip()
        affiliation_en = str(author.get("affiliation_en", "")).strip()

        if not name_ru:
            errors.append(f"author #{index}: empty Russian author name")
        if not name_en:
            errors.append(f"author #{index}: empty English author name")
        if not affiliation_ru:
            errors.append(f"author #{index}: empty Russian affiliation")
        if not affiliation_en:
            errors.append(f"author #{index}: empty English affiliation")
        if not email:
            errors.append(f"author #{index}: empty email")
        if email and not EMAIL_PATTERN.fullmatch(email):
            errors.append(f"author #{index}: invalid email `{email}`")
        if email and email in seen_emails:
            warnings.append(f"author #{index}: duplicate email `{email}`")
        seen_emails.add(email)

        if not orcid:
            errors.append(f"author #{index}: empty ORCID")
        if orcid and not ORCID_PATTERN.fullmatch(orcid):
            errors.append(f"author #{index}: invalid ORCID `{orcid}`")
        if orcid and orcid in seen_orcids and orcid != "0000-0000-0000-0000":
            warnings.append(f"author #{index}: duplicate ORCID `{orcid}`")
        seen_orcids.add(orcid)

        if _looks_like_placeholder(name_ru, language="ru"):
            placeholder_warnings.append(f"author #{index}: placeholder Russian author name `{name_ru}`")
        if _looks_like_placeholder(name_en, language="en"):
            placeholder_warnings.append(f"author #{index}: placeholder English author name `{name_en}`")
        if _looks_like_placeholder(affiliation_ru, language="ru"):
            placeholder_warnings.append(f"author #{index}: placeholder Russian affiliation `{affiliation_ru}`")
        if _looks_like_placeholder(affiliation_en, language="en"):
            placeholder_warnings.append(f"author #{index}: placeholder English affiliation `{affiliation_en}`")
        if email.endswith("@example.com"):
            placeholder_warnings.append(f"author #{index}: placeholder email `{email}`")
        if orcid == "0000-0000-0000-0000":
            placeholder_warnings.append(f"author #{index}: placeholder ORCID `{orcid}`")

    status = "ready"
    if errors:
        status = "invalid"
    elif placeholder_warnings:
        status = "template_placeholders_detected"
    elif warnings:
        status = "review_needed"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "placeholder_warnings": placeholder_warnings,
    }


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
        for key in ("name_ru", "name_en", "email", "orcid", "affiliation_ru", "affiliation_en"):
            if key not in author:
                raise KeyError(f"Article profile author #{index} is missing required key: {key}")
    analysis = analyze_article_profile(payload)
    if analysis["errors"]:
        raise ValueError("; ".join(analysis["errors"]))


def _looks_like_placeholder(value: str, *, language: str) -> bool:
    normalized = value.casefold()
    if not normalized:
        return True
    if language == "ru":
        return any(token in normalized for token in ("автор", "организация", "город", "страна"))
    return any(token in normalized for token in ("author", "organization", "city", "country"))
