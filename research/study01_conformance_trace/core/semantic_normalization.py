from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def semantic_intersection() -> dict[str, object]:
    return json.loads((ROOT / "config" / "semantic_intersection.json").read_text())


def primary_elements() -> list[dict[str, object]]:
    return [element for element in semantic_intersection()["elements"] if element["status"] == "MATCH"]  # type: ignore[index]


def assert_no_ambiguous_primary() -> None:
    ambiguous = [element["semantic_id"] for element in primary_elements() if element["status"] in {"AMBIGUOUS", "PARTIAL"}]
    if ambiguous:
        raise AssertionError(f"Primary matrix includes ambiguous semantics: {ambiguous}")
