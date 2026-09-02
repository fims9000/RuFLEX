"""Fail-closed S03 Phase 0 validator; no benchmark object is read or created."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;C=ROOT/'config'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 errors=[];m=json.loads((C/'phase0_manifest.json').read_text());matrix=json.loads((C/'matrix.json').read_text());corrupt=json.loads((C/'corruption_spec.json').read_text());rows=[json.loads(x) for x in (C/'locked_execution_plan.jsonl').read_text().splitlines() if x]
 expected=dict(m);expected.pop('manifest_id',None)
 if hashlib.sha256(json.dumps(expected,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=m.get('manifest_id'):errors.append('manifest identity mismatch')
 for name,digest in m['hashes'].items():
  if name.endswith('_sha256'):continue
  if sha(C/name)!=digest:errors.append(f'hash mismatch {name}')
 if m['hashes']['protocol_sha256']!=sha(ROOT/'PROTOCOL.md') or m['hashes']['statistical_plan_sha256']!=sha(ROOT/'STATISTICAL_ANALYSIS_PLAN.md'):errors.append('protocol/statistical plan hash mismatch')
 if len(matrix['datasets'])!=3 or set(matrix['models'])!={'logistic_regression','decision_tree','random_forest','gradient_boosting','flat_neuro_fuzzy'}:errors.append('locked matrix incomplete')
 if corrupt['severity']!={'LOW':.05,'MEDIUM':.25,'HIGH':.75}:errors.append('severity not frozen')
 if not rows or len({r['execution_id'] for r in rows})!=len(rows):errors.append('plan missing or duplicate IDs')
 if any(not r['benchmark_execution_forbidden'] for r in rows):errors.append('plan permits benchmark execution')
 if any((ROOT/'results').glob('**/*')):errors.append('S03 benchmark result artifact exists')
 if errors:raise SystemExit('S03 PHASE0 VALIDATOR FAIL: '+'; '.join(errors))
 print(f'S03 PHASE0 VALIDATOR PASS: {len(rows)} frozen executions; NO BENCHMARK RESULTS GENERATED')
if __name__=='__main__':main()
