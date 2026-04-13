from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal


ROOT = Path(__file__).resolve().parents[1]
REFERENCES_PATH = ROOT / "docs/article/article_references.json"
REFERENCE_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
PLACEHOLDER_TOKENS = ("todo", "tbd", "placeholder", "заполнить", "добавить")


def load_article_references() -> list[dict[str, str]]:
    payload = json.loads(REFERENCES_PATH.read_text(encoding="utf-8"))
    _validate_article_references(payload)
    return payload


def format_reference_lines(language: Literal["ru", "en"]) -> list[str]:
    return [str(item[language]).strip() for item in load_article_references()]


def analyze_article_references(payload: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    placeholder_warnings: list[str] = []
    seen_keys: set[str] = set()

    if not isinstance(payload, list) or not payload:
        errors.append("article_references.json must contain a non-empty list")
        return {
            "status": "invalid",
            "errors": errors,
            "warnings": warnings,
            "placeholder_warnings": placeholder_warnings,
        }

    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            errors.append(f"reference #{index}: entry must be an object")
            continue
        key = str(item.get("key", "")).strip()
        ru = str(item.get("ru", "")).strip()
        en = str(item.get("en", "")).strip()

        if not key:
            errors.append(f"reference #{index}: empty key")
        elif not REFERENCE_KEY_PATTERN.fullmatch(key):
            errors.append(f"reference #{index}: invalid key `{key}`")
        elif key in seen_keys:
            errors.append(f"reference #{index}: duplicate key `{key}`")
        seen_keys.add(key)

        if not ru:
            errors.append(f"reference #{index}: empty `ru` entry")
        if not en:
            errors.append(f"reference #{index}: empty `en` entry")

        for field_name, value in (("ru", ru), ("en", en)):
            normalized = value.casefold()
            if any(token in normalized for token in PLACEHOLDER_TOKENS):
                placeholder_warnings.append(
                    f"reference #{index} `{key}`: placeholder token detected in `{field_name}`"
                )
            if value.endswith(".."):
                warnings.append(f"reference #{index} `{key}`: suspicious punctuation in `{field_name}`")

    status = "ready"
    if errors:
        status = "invalid"
    elif placeholder_warnings:
        status = "review_needed"
    elif warnings:
        status = "review_needed"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "placeholder_warnings": placeholder_warnings,
    }


def _validate_article_references(payload: list[dict[str, Any]]) -> None:
    analysis = analyze_article_references(payload)
    if analysis["errors"]:
        raise ValueError("; ".join(analysis["errors"]))
