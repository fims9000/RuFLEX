from __future__ import annotations
import json
from pathlib import Path
import pytest
from research.s03_explanation_validation.sample_selection import select_validation_samples

def test_s03_sample_fallback_is_exact_and_fail_closed():
    rows=[{"source_row":i,"truth":0 if i<6 else 1,"prediction":0} for i in range(10)]
    assert [r["source_row"] for r in select_validation_samples(rows)] == [0, 1, 6, 7, 2, 3, 4, 5]
    with pytest.raises(ValueError,match="VALIDATION_SUPPORT_LT_8"): select_validation_samples(rows[:7])

def test_s03_phase02_plan_restores_clean_controls_and_component_applicability():
    root=Path(__file__).resolve().parents[1]/"research/s03_explanation_validation/config"
    rows=[json.loads(x) for x in (root/"locked_execution_plan_phase0_2.jsonl").read_text().splitlines()]
    assert len(rows)==18216
    assert sum(x["artifact_role"]=="CLEAN" for x in rows)==792
    assert sum(x["artifact_role"]=="CORRUPT" for x in rows)==17424
    assert all("component_applicability" in x for x in rows)

def test_s03_metric_only_does_not_count_numerical_warn_as_detector():
    root=Path(__file__).resolve().parents[1]/"research/s03_explanation_validation/config"
    spec=json.loads((root/"validator_spec_phase0_2.json").read_text())
    assert spec["native_numerical_semantics"]["numerical_completeness"]["WARN"] == "descriptive_only_not_detector"
