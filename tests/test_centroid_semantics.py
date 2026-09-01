from __future__ import annotations

import json

import numpy as np
import pytest

from ruflex.application.fis import (
    _rc21_semantic_hash,
    centroid_sample_coordinates,
    evaluate_fis,
    load_fis,
    persist_fis,
    reconstruct_mamdani_centroid_trace,
    semantic_hash,
)
from ruflex.domain.fis import (
    AntecedentClause,
    CentroidSampling,
    FISSpec,
    FuzzyRule,
    FuzzyVariable,
    MembershipFunction,
    OperatorSet,
)


def _m01(*, sampling: CentroidSampling = CentroidSampling.MIDPOINT_CELLS) -> FISSpec:
    terms = lambda: [MembershipFunction(name="low", parameters=(0.0, 0.0, 1.0)), MembershipFunction(name="high", parameters=(0.0, 1.0, 1.0))]
    return FISSpec(
        name="M01 centroid regression", inputs=[FuzzyVariable(name="x", minimum=0.0, maximum=1.0, terms=terms())],
        output=FuzzyVariable(name="y", minimum=0.0, maximum=1.0, role="output", terms=terms()),
        rules=[
            FuzzyRule(name="low", clauses=[AntecedentClause(variable="x", term="low")], output_term="low"),
            FuzzyRule(name="high", clauses=[AntecedentClause(variable="x", term="high")], output_term="high"),
        ], operators=OperatorSet(centroid_resolution=401, centroid_sampling=sampling),
    )


def test_centroid_inclusive_nodes_coordinates() -> None:
    coordinates, dx = centroid_sample_coordinates(0.0, 1.0, 5, CentroidSampling.INCLUSIVE_NODES)
    assert dx == pytest.approx(0.25)
    assert coordinates.tolist() == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_centroid_midpoint_cells_coordinates() -> None:
    coordinates, dx = centroid_sample_coordinates(0.0, 1.0, 4, CentroidSampling.MIDPOINT_CELLS)
    assert dx == pytest.approx(0.25)
    assert coordinates.tolist() == pytest.approx([0.125, 0.375, 0.625, 0.875])


def test_centroid_midpoint_matches_independent_oracle() -> None:
    grid = (np.arange(401, dtype=float) + 0.5) / 401.0
    aggregate = np.maximum(np.minimum(0.75, 1.0 - grid), np.minimum(0.25, grid))
    oracle = float((grid * aggregate).sum() / aggregate.sum())
    assert evaluate_fis(_m01(), {"x": 0.25}).output == pytest.approx(oracle, abs=1e-12)


def test_centroid_sampling_changes_semantic_hash() -> None:
    assert semantic_hash(_m01(sampling=CentroidSampling.INCLUSIVE_NODES)) != semantic_hash(_m01(sampling=CentroidSampling.MIDPOINT_CELLS))


def test_legacy_project_without_sampling_uses_inclusive_nodes(tmp_path) -> None:
    legacy = _m01(sampling=CentroidSampling.INCLUSIVE_NODES)
    payload = legacy.model_dump(mode="json")
    payload["schema_version"] = 1
    payload["operators"].pop("centroid_sampling")
    payload["operators"].pop("centroid_resolution")
    payload["semantic_hash"] = _rc21_semantic_hash(legacy)
    root = tmp_path / "project" / "models" / "fis"
    root.mkdir(parents=True)
    (root / f"{legacy.fis_id}.json").write_text(json.dumps(payload))
    (root / "active.txt").write_text(str(legacy.fis_id))
    restored = load_fis(tmp_path / "project")
    assert restored.operators.centroid_sampling is CentroidSampling.INCLUSIVE_NODES
    assert restored.operators.centroid_resolution == 401
    assert evaluate_fis(restored, {"x": 0.25}).output == pytest.approx(0.38507793017456354, abs=1e-12)


def test_new_project_centroid_defaults_to_midpoint_cells() -> None:
    assert _m01().operators.centroid_sampling is CentroidSampling.MIDPOINT_CELLS


def test_sampling_persists_close_reopen(tmp_path) -> None:
    persisted = persist_fis(tmp_path, _m01(sampling=CentroidSampling.INCLUSIVE_NODES))
    restored = load_fis(tmp_path)
    assert restored.operators.centroid_sampling is CentroidSampling.INCLUSIVE_NODES
    assert restored.semantic_hash == persisted.semantic_hash


def test_exact_trace_records_centroid_sampling() -> None:
    trace = evaluate_fis(_m01(), {"x": 0.25}).trace
    assert trace.centroid_sampling is CentroidSampling.MIDPOINT_CELLS
    assert trace.centroid_resolution == 401
    assert trace.centroid_sample_count == 401
    assert trace.centroid_dx == pytest.approx(1 / 401)
    assert trace.output_domain == (0.0, 1.0)


@pytest.mark.parametrize("sampling", [CentroidSampling.MIDPOINT_CELLS, CentroidSampling.INCLUSIVE_NODES])
def test_trace_reconstruction_uses_declared_centroid_sampling(sampling: CentroidSampling) -> None:
    evaluation = evaluate_fis(_m01(sampling=sampling), {"x": 0.25})
    assert reconstruct_mamdani_centroid_trace(evaluation.trace) == pytest.approx(evaluation.output, abs=1e-12)


def test_invalid_centroid_resolution_and_unknown_sampling_are_rejected() -> None:
    with pytest.raises(ValueError, match="Inclusive-node"):
        OperatorSet(centroid_resolution=1, centroid_sampling=CentroidSampling.INCLUSIVE_NODES)
    with pytest.raises(ValueError):
        OperatorSet.model_validate({"centroid_sampling": "unknown"})
