from pathlib import Path
from research.study02_protocol_integrity.core.audit_runner import exercise_preventable
def test_real_product_preventable_entry_points(tmp_path:Path):
 for family in ('V01','V06','V07'):
  result=exercise_preventable(family,tmp_path/family)
  assert result['entry_point'].startswith('ruflex.') and result['invalid_artifact_persisted'] is False
def test_subject_adapter_has_no_oracle_or_marker_mapping():
 text=(Path(__file__).resolve().parents[1]/'core/ruflex_subject.py').read_text().lower()
 assert 'scenario_ground_truth' not in text and 'from research.study02_protocol_integrity.oracle' not in text
 assert "'preprocessing_fit_scope'" not in text and 'preprocessing_fit_scope=' in text
