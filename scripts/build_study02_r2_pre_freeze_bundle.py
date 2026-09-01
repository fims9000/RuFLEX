"""Build the immutable-inspection Study 02 R2 pre-freeze review ZIP."""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/STUDY02_R2_CONFIRMATORY_PRE_FREEZE.zip'
TOP='STUDY02_R2_CONFIRMATORY_PRE_FREEZE'
FILES=[
 ROOT/'research/study02_protocol_integrity/POST_FREEZE_SCIENTIFIC_AUDIT.md',
 ROOT/'research/study02_protocol_integrity/core/ruflex_subject.py',
 ROOT/'research/study02_protocol_integrity/scripts/locked_executor.py',
 ROOT/'research/study02_r2_confirmatory/PROTOCOL.md',
 ROOT/'research/study02_r2_confirmatory/DECISIONS.md',
 ROOT/'research/study02_r2_confirmatory/core.py',
 ROOT/'research/study02_r2_confirmatory/scripts.py',
 ROOT/'research/study02_r2_confirmatory/config/locked_manifest.json',
 ROOT/'research/study02_r2_confirmatory/config/locked_execution_plan.jsonl',
 ROOT/'research/study02_r2_confirmatory/artifacts/dev.json',
 ROOT/'research/study02_r2_confirmatory/tests/test_r2.py',
 ROOT/'release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip',
]
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 auth=ROOT/'.agent-state/STUDY02_R2_TEST_AUTHORIZATION.json';locked=ROOT/'research/study02_r2_confirmatory/artifacts/raw/locked_outcomes.jsonl'
 if auth.exists() or locked.exists():raise RuntimeError('R2 is not pre-freeze: authorization or locked outcomes exist.')
 manifest=json.loads((ROOT/'research/study02_r2_confirmatory/config/locked_manifest.json').read_text());checks={str(path.relative_to(ROOT)):sha(path) for path in FILES}
 bundle={'schema_version':1,'kind':'Study 02 R2 pre-freeze protocol-review bundle','product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'execution_plan_sha':manifest['plan_sha'],'locked_outcomes_executed':'NO','files':checks}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as archive:
  for path in FILES:archive.write(path,f'{TOP}/{path.relative_to(ROOT)}')
  archive.writestr(f'{TOP}/BUNDLE_MANIFEST.json',json.dumps(bundle,indent=2,sort_keys=True)+'\n')
  archive.writestr(f'{TOP}/SHA256SUMS.txt',''.join(f'{digest}  {name}\n' for name,digest in checks.items()))
 print(f'{OUT}\nsha256={sha(OUT)}')
if __name__=='__main__':main()
