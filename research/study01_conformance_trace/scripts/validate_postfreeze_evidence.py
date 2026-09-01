from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 assert hashlib.sha256((ROOT.parents[1]/'release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip').read_bytes()).hexdigest()=='772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224'
 assert hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest()=='fca2df2dc95318486c4c596905242d96d5fd5540311bfe4a7853e25d290e6838'
 assert hashlib.sha256((ROOT/'artifacts/locked/locked_study_results.json').read_bytes()).hexdigest()=='99fa45340cd6c9250f972e957cca9bc513bdc2a377328d3f4a3db29118d7f19e'
 r=json.loads((ROOT/'artifacts/diagnostics/reproduction_summary.json').read_text()); d=json.loads((ROOT/'artifacts/diagnostics/no_rule_boundary_analysis.json').read_text())
 assert r['matches_original'] and sum(d['classification_counts'].values())==4056
 assert (ROOT/r['raw_artifact']).is_file()
 for prefix in ('T01_locked_system_summary','T02_semantic_compatibility','T03_failure_taxonomy','T04_defined_output_conformance','T05_trace_roundtrip_summary','T06_boundary_diagnostics'):
  assert any((ROOT/'tables').glob(prefix+'*'))
 for n in range(1,7):
  stem=f'F0{n}_'; assert any((ROOT/'figures/manuscript').glob(stem+'*.svg')); assert any((ROOT/'figures/manuscript').glob(stem+'*.meta.json'))
 assert 'C1' in (ROOT/'THESIS_EVIDENCE.md').read_text() and (ROOT/'RESULT_FREEZE_ADDENDUM.md').is_file()
 print('STUDY01_POST_FREEZE_EVIDENCE_VALIDATOR_PASS')
if __name__=='__main__': main()
