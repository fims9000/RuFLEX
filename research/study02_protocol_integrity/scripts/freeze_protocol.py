from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['PROTOCOL.md','MASTER_SPEC.md','config/study02.yaml','config/detectability_matrix.json','config/severity_policy.json','config/violation_families.json','config/tolerances_or_thresholds.json','config/environments.json','config/locked_scenarios.jsonl','artifacts/diagnostics/locked_pair_diffs.jsonl','artifacts/diagnostics/materialized_scenarios.jsonl','artifacts/manifests/locked_execution_plan.jsonl']
for folder in ('baselines','core','generators','mutations','scripts','oracle'):
 FILES.extend(str(p.relative_to(ROOT)) for p in sorted((ROOT/folder).glob('*.py')))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 hashes={name:digest(ROOT/name) for name in FILES}; protocol=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(); matrix=json.loads((ROOT/'config/detectability_matrix.json').read_text()); supported=[x['id'] for x in matrix if x['status'].startswith('SUPPORTED')]
 pairs=sum(1 for _ in (ROOT/'config/locked_scenarios.jsonl').read_text().splitlines())
 plan=ROOT/'artifacts/manifests/locked_execution_plan.jsonl'
 manifest={'schema_version':4,'status':'PROTOCOL_FROZEN_AWAITING_EXTERNAL_AUTHORIZATION','product_sha256':'772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224','protocol_hash':protocol,'file_hashes':hashes,'supported_families':supported,'locked_pairs_per_family':20,'locked_pairs':pairs,'locked_scenarios':pairs*2,'locked_execution_plan_sha256':digest(plan),'authorization_record_path':'.agent-state/STUDY02_TEST_AUTHORIZATION.json','authorization_is_external_to_manifest':True}
 manifest['manifest_hash']=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(); (ROOT/'config/locked_suite_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');print(json.dumps({'protocol_hash':protocol,'manifest_hash':manifest['manifest_hash'],'supported':supported},sort_keys=True))
if __name__=='__main__':main()
