"""Standalone A02 regression and negative tests."""
import math
from pathlib import Path

import pytest

from certificates import (audit_reference, binary_threshold_certificate,
    exact_one_sided_lower, min_perfect_runs, multiclass_margin_certificate,
    read_calibration_csv, read_reference_csv)


def test_exact_all_agree():
    assert exact_one_sided_lower(19, 19, .05) == pytest.approx(.05 ** (1 / 19))
    assert min_perfect_runs(.95, .05) == 59
    assert exact_one_sided_lower(59, 59, .05) >= .95
    assert exact_one_sided_lower(0, 60, .05) == 0
    assert exact_one_sided_lower(35, 60, .05) < 35 / 60


def test_bound_matches_scipy():
    from scipy.stats import beta
    for n in (5, 19, 59, 100):
        for k in (1, n // 2, n - 1):
            assert exact_one_sided_lower(k, n, .05) == pytest.approx(beta.ppf(.05, k, n - k + 1), abs=1e-12)


def test_deterministic_margin_not_confidence():
    assert multiclass_margin_certificate([0.9, 0.2, 0.1], .3)
    assert not multiclass_margin_certificate([0.9, 0.4], .3)
    assert binary_threshold_certificate(.90, .78, .10)
    assert not binary_threshold_certificate(.90, .85, .08)
    with pytest.raises(ValueError):
        binary_threshold_certificate(.9, .0, .1)


def test_audit_independence_and_multiplicity():
    refs = {"a": "1", "b": "0"}
    cal = {"a": {s: "1" for s in range(100, 160)},
           "b": {s: "0" for s in range(100, 160)}}
    point = audit_reference(refs, cal, declared_seeds=list(range(100, 160)), correction="none", reference_seed=7)
    joint = audit_reference(refs, cal, declared_seeds=list(range(100, 160)), reference_seed=7)
    assert point[0]["certified"]
    assert joint[0]["one_sided_lower_bound"] < point[0]["one_sided_lower_bound"]
    with pytest.raises(ValueError, match="reference seed"):
        audit_reference(refs, cal, declared_seeds=list(range(100, 160)), reference_seed=111)
    with pytest.raises(ValueError, match="missing or extra"):
        audit_reference(refs, {"a": {100: "1"}, "b": cal["b"]}, declared_seeds=list(range(100, 160)))


def test_csv_duplicates_rejected(tmp_path: Path):
    ref = tmp_path / "ref.csv"
    ref.write_text("case_id,reference_class,reference_seed\na,1,9000\nb,0,9000\n")
    got, seed = read_reference_csv(ref)
    assert got == {"a":"1", "b":"0"} and seed == 9000
    cal = tmp_path / "cal.csv"
    cal.write_text("case_id,seed,prediction\na,100,1\na,100,0\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_calibration_csv(cal)