from __future__ import annotations

import pytest

from research.study01_conformance_trace.adapters.pyfuzzylite_adapter import ReferenceUnavailable, evaluate as reference_evaluate
from research.study01_conformance_trace.adapters.ruflex_adapter import evaluate as subject_evaluate
from research.study01_conformance_trace.fixtures.catalog import dev_mamdani, dev_sugeno
from ruflex.domain.fis import CentroidSampling


def test_ruflex_adapter_mapping() -> None:
    assert subject_evaluate(dev_sugeno(), {"x": 0.25}).output == pytest.approx(0.35)


def test_pyfuzzylite_adapter_mapping() -> None:
    assert reference_evaluate(dev_sugeno(), {"x": 0.25}) == pytest.approx(0.35, abs=1e-10)


def test_fuzzylite_dev_m01_midpoint_conformance() -> None:
    subject = subject_evaluate(dev_mamdani(), {"x": 0.25}).output
    reference = reference_evaluate(dev_mamdani(), {"x": 0.25})
    assert subject == pytest.approx(reference, abs=1e-10)


def test_legacy_mamdani_is_refused_for_midpoint_reference_comparison() -> None:
    legacy = dev_mamdani().model_copy(update={"operators": dev_mamdani().operators.model_copy(update={"centroid_sampling": CentroidSampling.INCLUSIVE_NODES})})
    with pytest.raises(ReferenceUnavailable, match="midpoint-cell"):
        reference_evaluate(legacy, {"x": 0.25})


def test_unsupported_reference_mapping_fails_closed() -> None:
    spec = dev_sugeno().model_copy(update={"operators": dev_sugeno().operators.model_copy(update={"and_operator": "product"})})
    with pytest.raises(ReferenceUnavailable):
        reference_evaluate(spec, {"x": 0.5})
