from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from article_profile import (
    PROFILE_PATH,
    PROFILE_TEMPLATE_PATH,
    analyze_article_profile,
    format_affiliations,
    format_author_names,
    format_emails,
    format_keywords,
    format_orcids,
)
from render_article_profile_docs import render_article_profile_docs


ROOT = Path(__file__).resolve().parents[1]
ROOT_FIELDS = {
    "title_ru",
    "title_en",
    "funding_ru",
    "funding_en",
    "acknowledgment_ru",
    "acknowledgment_en",
}
AUTHOR_FIELDS = {
    "name_ru",
    "name_en",
    "email",
    "orcid",
    "affiliation_ru",
    "affiliation_en",
}
REQUIRED_AUTHOR_FIELDS = (
    "name_ru",
    "name_en",
    "email",
    "orcid",
    "affiliation_ru",
    "affiliation_en",
)


def main() -> None:
    try:
        _main()
    except Exception as error:
        print(f"manage_article_profile.py: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def _main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or update docs/article/article_profile.json.")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print the current profile summary. This is also the default when no updates are passed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the resulting profile as JSON instead of a text summary.",
    )
    parser.add_argument(
        "--set",
        dest="root_updates",
        action="append",
        default=[],
        help="Update a root field using key=value. Supported keys: title_ru, title_en, funding_ru, funding_en, acknowledgment_ru, acknowledgment_en.",
    )
    parser.add_argument(
        "--keywords-ru",
        default=None,
        help="Replace Russian keywords using a semicolon-separated list.",
    )
    parser.add_argument(
        "--keywords-en",
        default=None,
        help="Replace English keywords using a semicolon-separated list.",
    )
    parser.add_argument(
        "--author-set",
        dest="author_updates",
        action="append",
        default=[],
        help="Update an author field using index:key=value, where index starts at 1.",
    )
    parser.add_argument(
        "--author-add",
        dest="author_additions",
        action="append",
        default=[],
        help="Append a new author using key=value pairs separated by `|`.",
    )
    parser.add_argument(
        "--author-remove",
        dest="author_removals",
        action="append",
        default=[],
        help="Remove an author by 1-based index. Can be passed multiple times.",
    )
    parser.add_argument(
        "--reset-from-template",
        action="store_true",
        help="Replace docs/article/article_profile.json with the current template before applying updates.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Force re-rendering of generated article docs. Updates trigger sync automatically.",
    )
    args = parser.parse_args()

    profile = load_profile_for_edit(reset_from_template=args.reset_from_template)
    mutated = args.reset_from_template

    for item in args.root_updates:
        key, value = _parse_root_update(item)
        profile[key] = value
        mutated = True

    if args.keywords_ru is not None:
        profile["keywords_ru"] = _parse_keywords(args.keywords_ru)
        mutated = True
    if args.keywords_en is not None:
        profile["keywords_en"] = _parse_keywords(args.keywords_en)
        mutated = True

    if args.author_removals:
        removal_indexes = sorted({_parse_author_index(item) for item in args.author_removals}, reverse=True)
        for author_index in removal_indexes:
            if author_index >= len(profile["authors"]):
                raise ValueError(f"Author index out of range: {author_index + 1}")
            if len(profile["authors"]) == 1:
                raise ValueError("Cannot remove the last remaining author from article_profile.json")
            profile["authors"].pop(author_index)
            mutated = True

    for item in args.author_additions:
        profile["authors"].append(_parse_author_addition(item))
        mutated = True

    for item in args.author_updates:
        author_index, key, value = _parse_author_update(item)
        if author_index >= len(profile["authors"]):
            raise ValueError(f"Author index out of range: {author_index + 1}")
        profile["authors"][author_index][key] = value
        mutated = True

    analysis = analyze_article_profile(profile)
    _raise_if_invalid(profile, analysis)

    if mutated:
        write_article_profile(profile)
    if mutated or args.sync:
        render_article_profile_docs()

    if args.json:
        print(json.dumps(profile, indent=2, ensure_ascii=False))
        return
    print(render_article_profile_summary(profile, analysis))


def load_profile_for_edit(*, reset_from_template: bool) -> dict[str, Any]:
    source_path = PROFILE_TEMPLATE_PATH if reset_from_template else (PROFILE_PATH if PROFILE_PATH.exists() else PROFILE_TEMPLATE_PATH)
    return json.loads(source_path.read_text(encoding="utf-8"))


def write_article_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def render_article_profile_summary(profile: dict[str, Any], analysis: dict[str, Any]) -> str:
    lines = [
        "# RuFLEX article profile",
        "",
        f"- path: `{PROFILE_PATH}`",
        f"- status: `{analysis['status']}`",
        f"- authors_ru: `{format_author_names(profile, language='ru')}`",
        f"- authors_en: `{format_author_names(profile, language='en')}`",
        f"- emails: `{format_emails(profile)}`",
        f"- orcids: `{format_orcids(profile)}`",
        f"- keywords_ru: `{format_keywords(profile['keywords_ru'])}`",
        f"- keywords_en: `{format_keywords(profile['keywords_en'])}`",
        "",
        "## Authors",
        "",
    ]
    for index, author in enumerate(profile["authors"], start=1):
        lines.extend(
            [
                f"- `{index}` {author['name_ru']} / {author['name_en']} | {author['email']} | ORCID {author['orcid']}",
                f"  {author['affiliation_ru']} / {author['affiliation_en']}",
            ]
        )
    lines.extend(
        [
            "",
        "## Affiliations RU",
        "",
        ]
    )
    for item in format_affiliations(profile, language="ru"):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Affiliations EN", ""])
    for item in format_affiliations(profile, language="en"):
        lines.append(f"- `{item}`")
    if analysis["warnings"] or analysis["placeholder_warnings"]:
        lines.extend(["", "## Review", ""])
        for item in analysis["warnings"]:
            lines.append(f"- `warning` {item}")
        for item in analysis["placeholder_warnings"]:
            lines.append(f"- `placeholder` {item}")
    return "\n".join(lines)


def _parse_root_update(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise ValueError(f"Expected key=value, got: {raw}")
    key, value = raw.split("=", 1)
    key = key.strip()
    if key not in ROOT_FIELDS:
        raise KeyError(f"Unsupported root article_profile field: {key}")
    return key, value.strip()


def _parse_author_update(raw: str) -> tuple[int, str, str]:
    if ":" not in raw or "=" not in raw:
        raise ValueError(f"Expected index:key=value, got: {raw}")
    index_text, rest = raw.split(":", 1)
    key, value = rest.split("=", 1)
    author_index = _parse_author_index(index_text)
    key = key.strip()
    if key not in AUTHOR_FIELDS:
        raise KeyError(f"Unsupported author field: {key}")
    return author_index, key, value.strip()


def _parse_author_addition(raw: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for item in raw.split("|"):
        chunk = item.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"Expected key=value inside --author-add, got: {chunk}")
        key, value = chunk.split("=", 1)
        key = key.strip()
        if key not in AUTHOR_FIELDS:
            raise KeyError(f"Unsupported author field in --author-add: {key}")
        payload[key] = value.strip()
    missing = [key for key in REQUIRED_AUTHOR_FIELDS if not payload.get(key)]
    if missing:
        raise ValueError(f"--author-add is missing required fields: {', '.join(missing)}")
    return payload


def _parse_author_index(raw: str) -> int:
    try:
        author_index = int(str(raw).strip()) - 1
    except ValueError as error:
        raise ValueError(f"Author index must be an integer, got: {raw}") from error
    if author_index < 0:
        raise ValueError("Author index starts at 1.")
    return author_index


def _parse_keywords(raw: str) -> list[str]:
    items = [item.strip() for item in raw.split(";")]
    values = [item for item in items if item]
    if not values:
        raise ValueError("Keywords list must contain at least one non-empty item.")
    return values


def _raise_if_invalid(profile: dict[str, Any], analysis: dict[str, Any]) -> None:
    for item in analysis["errors"]:
        raise ValueError(item)


if __name__ == "__main__":
    main()
