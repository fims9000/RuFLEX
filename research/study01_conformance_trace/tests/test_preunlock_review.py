from __future__ import annotations

from research.study01_conformance_trace.scripts.check_reference_determinism import run
from research.study01_conformance_trace.scripts.diagnose_mamdani_centroid import diagnose


def test_reference_environment_outputs_are_repeatable() -> None:
    result = run()
    assert result["deterministic_bitwise_float_equality"] is True
    assert result["reference"] == {"pyfuzzylite": "8.0.6", "numpy": "1.26.4"}


def test_mamdani_difference_is_classified_without_tolerance_change() -> None:
    result = diagnose()
    assert result["classification"] == "NUMERICAL_DISCRETIZATION_DIFFERENCE"
    assert result["ruflex_output"] == result["ruflex_declared_formula_output"]
    assert result["declared_401_absolute_error"] > 1e-5
    assert result["no_rule_default_behavior"]["ruflex"].startswith("EXCEPTION:")
    assert result["no_rule_default_behavior"]["pyfuzzylite"] == "NAN_DEFAULT"
