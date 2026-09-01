from __future__ import annotations

from research.study01_conformance_trace.fixtures.generator import generated_fixtures


def test_generated_fixture_reproducible() -> None:
    first = generated_fixtures("mamdani", seed=20260831)
    second = generated_fixtures("mamdani", seed=20260831)
    assert [item.semantic_hash for item in first.values()] == [item.semantic_hash for item in second.values()]
    assert len(first) == 20
