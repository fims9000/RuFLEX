"""Build the inspection-first Study 02 protocol-review bundle."""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; STUDY=ROOT/'research/study02_protocol_integrity'; OUT=ROOT/'release/STUDY02_PROTOCOL_INTEGRITY_REMEDIATED_PRE_FREEZE.zip'; TOP='STUDY02_PROTOCOL_INTEGRITY_REMEDIATED_PRE_FREEZE'
SKIP={'__pycache__','.pytest_cache','node_modules','.venv','.git'}
def ok(p): return not any(x in SKIP for x in p.parts) and p.suffix not in {'.pyc','.pyo'}
def main():
 files=sorted(p for p in STUDY.rglob('*') if p.is_file() and ok(p.relative_to(ROOT)))+[ROOT/'release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip']
 checks={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 manifest={'schema_version':1,'kind':'Study 02 remediated pre-freeze protocol-review bundle','product_sha256':'772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224','protocol_sha256':'fae85459726afc5ab94714ea80a5c0cf6b473ee6494b1b02969bcf5d0c3062ab','locked_manifest_id':'6bf4ac4d9c37ccd2399b4465cbf8d778451bb34faaedd5e92f186d25bdf56272','locked_scenario_spec_sha256':'8b45286038d2ddd59953fe553671c9671bed350724a4e02f2dc708adc1cf4c6c','test_unlock':'FORBIDDEN_PENDING_PROTOCOL_REVIEW','supersedes_before_test_unlock':{'protocol_sha256':'69b2fe941450de3c6798d53ba563ac4b7dd59c3be63574e9747b54efa8162f02','locked_manifest_id':'bc466c520fd565d03e069ad602c2c5ec3ec6f6fd2402714c51572305483c8499'},'files':checks}
 with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
  for p in files:z.write(p,f'{TOP}/{p.relative_to(ROOT)}')
  z.writestr(f'{TOP}/BUNDLE_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n');z.writestr(f'{TOP}/SHA256SUMS.txt',''.join(f'{d}  {n}\n' for n,d in checks.items()))
 print(f'{OUT}\nsha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}\nfiles={len(files)}')
if __name__=='__main__':main()
