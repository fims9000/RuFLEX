from __future__ import annotations
from pathlib import Path
import pytest
from research.a01_stability_aware_review.scripts.execute_phase2_final_test import RESULT_SCHEMA, authorization_gate
from research.a01_stability_aware_review.statistics import paired_bootstrap_policy_metrics

ROOT=Path(__file__).resolve().parents[1]/"research/a01_stability_aware_review"

def test_phase2_forbids_training_and_tuning_paths() -> None:
 source=(ROOT/"scripts/execute_phase2_final_test.py").read_text()
 for forbidden in ("train_model","create_training_study","select_validation_threshold","create_selective_policy","create_stability_gate_policy"):
  assert forbidden not in source
 assert "evaluate_final_test" in source

def test_phase2_unlock_rejects_missing_and_bad_identity(tmp_path:Path) -> None:
 with pytest.raises(PermissionError):authorization_gate(None,{"phase1_5_manifest_id":"x"})
 p=tmp_path/"unlock.json";p.write_text('{"study":"A01","allow_single_final_test_opening":true,"authorized_at":"x","phase1_5_manifest_id":"wrong"}')
 with pytest.raises(PermissionError):authorization_gate(p,{"phase1_5_manifest_id":"x"})

def test_frozen_bootstrap_has_all_required_statistics() -> None:
 out=paired_bootstrap_policy_metrics([0,1,1,0],[0,1,0,0],["ACCEPT","ACCEPT","REVIEW","ACCEPT"],["ACCEPT","ACCEPT","ACCEPT","ACCEPT"],replicates=100,seed=20260902)
 assert out["bootstrap_seed"]==20260902 and out["replicates"]==100
 assert out["delta_risk"]["requested_replicates"]==100
 assert "percentile_ci_95" in out["delta_coverage"] and "percentile_ci_95" in out["delta_fnr"]

def test_result_schema_has_frozen_tables_and_figures() -> None:
 assert RESULT_SCHEMA["tables"]==["T05_final_test_policy_outcomes.csv","T06_h3_effects.csv","T07_ai4i_fnr.csv","T08_final_scientific_status.csv"]
 assert len(RESULT_SCHEMA["figures"])==4
