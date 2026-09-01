from __future__ import annotations

from research.study01_conformance_trace.core.semantic_normalization import assert_no_ambiguous_primary, primary_elements, semantic_intersection


def test_semantic_intersection_schema() -> None:
    data = semantic_intersection()
    assert data["schema_version"] == 1
    assert all({"semantic_id", "ruflex", "reference", "status", "reason", "source"}.issubset(element) for element in data["elements"])


def test_no_ambiguous_semantics_in_primary_matrix() -> None:
    assert primary_elements()
    assert_no_ambiguous_primary()
