from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_detector_does_not_import_or_read_oracle():
 for path in [ROOT/'core/audit_runner.py',ROOT/'baselines/basic_manifest_audit.py']:
  text=path.read_text(); assert 'oracle' not in text.lower()
