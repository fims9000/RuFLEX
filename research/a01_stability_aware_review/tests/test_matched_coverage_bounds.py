"""Counterexample and exhaustive checks for matched-coverage A01 bounds."""
from __future__ import annotations

from itertools import combinations, product
import importlib.util
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "bound_matched_coverage_a01.py"
spec = importlib.util.spec_from_file_location("a01_matched_coverage", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
bounds = module.sharp_baseline_bounds


def test_bank_marketing_proven_minimum_eleven_additional_errors():
    assert bounds(8238, 1386, 7125, 606, 7523) == (671, 1004)


def test_ai4i_advantage_not_identified_at_equal_coverage():
    assert bounds(2000, 52, 2000, 52, 1966) == (18, 52)


def test_inconsistent_error_counts_fail_closed():
    with pytest.raises(ValueError):
        bounds(10, 4, 10, 1, 5)


def test_exhaustive_sharpness_through_five_cases():
    for n in range(1, 6):
        ids = set(range(n))
        for errors in product((0, 1), repeat=n):
            for old_flags in product((0, 1), repeat=n):
                old = {i for i, flag in enumerate(old_flags) if flag}
                ea = sum(errors[i] for i in old)
                for target in range(n + 1):
                    if target <= len(old):
                        subsets = (set(v) for v in combinations(old, target))
                    else:
                        subsets = (old | set(v) for v in combinations(ids - old, target - len(old)))
                    possibilities = [sum(errors[i] for i in subset) for subset in subsets]
                    assert bounds(n, sum(errors), len(old), ea, target) == (
                        min(possibilities), max(possibilities),
                    )


def test_original_a01_freeze_and_all_fifteen_cells():
    results = module.audit()
    assert len(results["rows"]) == 15
    bank = next(x for x in results["rows"]
                if x["dataset"] == "uci_bank_marketing" and x["model"] == "decision_tree")
    assert (bank["confidence_matched_min_errors"], bank["confidence_matched_max_errors"]) == (671, 1004)
    assert bank["min_gate_excess_errors_vs_any_baseline_extension"] == 11
    statuses = [x["status"] for x in results["rows"]]
    assert statuses.count("GATE_WORSE_FOR_EVERY_FEASIBLE_BASELINE_MATCH") == 1
    assert statuses.count("GATE_BETTER_FOR_EVERY_FEASIBLE_BASELINE_MATCH") == 0
