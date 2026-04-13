from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from article_references import REFERENCES_PATH, analyze_article_references
from render_article_profile_docs import render_reference_docs


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_FIELDS = {"key", "ru", "en"}


def main() -> None:
    try:
        _main()
    except Exception as error:
        print(f"manage_article_references.py: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def _main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or update docs/article/article_references.json.")
    parser.add_argument("--show", action="store_true", help="Print the current reference summary.")
    parser.add_argument("--json", action="store_true", help="Print the resulting references as JSON.")
    parser.add_argument(
        "--set",
        dest="updates",
        action="append",
        default=[],
        help="Update a reference using key:field=value, where field is one of key, ru, en.",
    )
    parser.add_argument(
        "--add",
        dest="additions",
        action="append",
        default=[],
        help="Append a reference using key=value pairs separated by `|`.",
    )
    parser.add_argument(
        "--remove",
        dest="removals",
        action="append",
        default=[],
        help="Remove a reference by its key. Can be passed multiple times.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Force regeneration of references_ru_gost.md and references_en_ieee.md.",
    )
    args = parser.parse_args()

    references = load_references_for_edit()
    mutated = False

    if args.removals:
        removal_keys = {item.strip() for item in args.removals if item.strip()}
        if removal_keys:
            existing = {str(item["key"]).strip() for item in references}
            missing = sorted(removal_keys - existing)
            if missing:
                raise KeyError(f"Unknown reference key(s): {', '.join(missing)}")
            references = [item for item in references if str(item["key"]).strip() not in removal_keys]
            mutated = True

    for raw in args.additions:
        entry = _parse_reference_addition(raw)
        if any(str(item["key"]).strip() == entry["key"] for item in references):
            raise ValueError(f"Reference key already exists: {entry['key']}")
        references.append(entry)
        mutated = True

    for raw in args.updates:
        reference_key, field_name, value = _parse_reference_update(raw)
        matched = next((item for item in references if str(item["key"]).strip() == reference_key), None)
        if matched is None:
            raise KeyError(f"Unknown reference key: {reference_key}")
        if field_name == "key" and any(
            str(item["key"]).strip() == value for item in references if item is not matched
        ):
            raise ValueError(f"Reference key already exists: {value}")
        matched[field_name] = value
        mutated = True

    analysis = analyze_article_references(references)
    _raise_if_invalid(analysis)

    if mutated:
        write_article_references(references)
    if mutated or args.sync:
        render_reference_docs()

    if args.json:
        print(json.dumps(references, indent=2, ensure_ascii=False))
        return
    print(render_article_references_summary(references, analysis))


def load_references_for_edit() -> list[dict[str, str]]:
    return json.loads(REFERENCES_PATH.read_text(encoding="utf-8"))


def write_article_references(payload: list[dict[str, str]]) -> None:
    REFERENCES_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def render_article_references_summary(
    references: list[dict[str, str]],
    analysis: dict[str, Any],
) -> str:
    lines = [
        "# RuFLEX article references",
        "",
        f"- path: `{REFERENCES_PATH}`",
        f"- status: `{analysis['status']}`",
        f"- count: `{len(references)}`",
        "",
        "## Entries",
        "",
    ]
    for item in references:
        lines.append(f"- `{item['key']}`")
        lines.append(f"  RU: {item['ru']}")
        lines.append(f"  EN: {item['en']}")
    if analysis["warnings"] or analysis["placeholder_warnings"]:
        lines.extend(["", "## Review", ""])
        for item in analysis["warnings"]:
            lines.append(f"- `warning` {item}")
        for item in analysis["placeholder_warnings"]:
            lines.append(f"- `placeholder` {item}")
    return "\n".join(lines)


def _parse_reference_update(raw: str) -> tuple[str, str, str]:
    if ":" not in raw or "=" not in raw:
        raise ValueError(f"Expected key:field=value, got: {raw}")
    reference_key, rest = raw.split(":", 1)
    field_name, value = rest.split("=", 1)
    reference_key = reference_key.strip()
    field_name = field_name.strip()
    if not reference_key:
        raise ValueError("Reference key must not be empty.")
    if field_name not in REFERENCE_FIELDS:
        raise KeyError(f"Unsupported reference field: {field_name}")
    value = value.strip()
    if not value:
        raise ValueError(f"Reference field `{field_name}` must not be empty.")
    return reference_key, field_name, value


def _parse_reference_addition(raw: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for item in raw.split("|"):
        chunk = item.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"Expected key=value inside --add, got: {chunk}")
        key, value = chunk.split("=", 1)
        key = key.strip()
        if key not in REFERENCE_FIELDS:
            raise KeyError(f"Unsupported reference field in --add: {key}")
        payload[key] = value.strip()
    missing = [field_name for field_name in REFERENCE_FIELDS if not payload.get(field_name)]
    if missing:
        raise ValueError(f"--add is missing required fields: {', '.join(sorted(missing))}")
    return payload


def _raise_if_invalid(analysis: dict[str, Any]) -> None:
    if analysis["errors"]:
        raise ValueError("; ".join(analysis["errors"]))


if __name__ == "__main__":
    main()
