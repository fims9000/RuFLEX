"""Build an inspection-first Study 02 result-freeze bundle."""
from __future__ import annotations
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'research/study02_protocol_integrity'
OUT=ROOT/'release/STUDY02_PROTOCOL_INTEGRITY_RESULT_FREEZE.zip'
TOP='STUDY02_PROTOCOL_INTEGRITY_RESULT_FREEZE'
SKIP={'__pycache__','.pytest_cache','node_modules','.venv','.git'}

def keep(path:Path)->bool:
 parts=path.parts
 return not any(part in SKIP for part in parts) and ('artifacts','raw','projects') not in tuple(parts[index:index+3] for index in range(len(parts)-2)) and path.suffix not in {'.pyc','.pyo','.sqlite'}

def main()->None:
 files=sorted(path for path in STUDY.rglob('*') if path.is_file() and keep(path.relative_to(ROOT)))
 files += [ROOT/'.agent-state/STUDY02_TEST_AUTHORIZATION.json',ROOT/'.agent-state/STUDY02_TASK_STATE.json',ROOT/'release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip']
 checks={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
 manifest={'schema_version':1,'kind':'Study 02 result-freeze inspection bundle','product_sha256':'772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224','protocol_sha256':'b2a15c5084e54afdc6f076625e1de85ea681ad171c8c8f53422f48ccd9139a54','manifest_id':'59eb5ae15fa84b810e20c16437ca641fd89d5afcd1de3ba5028ae54fa47faf95','execution_plan_sha256':'fede3ee5e914099b6f65df7343a8bc0d2d6b62d83da7f5d8564e08e44e8a0b4c','raw_sha256':'5e217b593051cbd509ba7a20e25da66ac3b49d0b752ec535931b18687af4ba0e','files':checks}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as bundle:
  for path in files: bundle.write(path,f'{TOP}/{path.relative_to(ROOT)}')
  bundle.writestr(f'{TOP}/BUNDLE_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
  bundle.writestr(f'{TOP}/SHA256SUMS.txt',''.join(f'{digest}  {name}\n' for name,digest in checks.items()))
 print(f'{OUT}\nsha256={hashlib.sha256(OUT.read_bytes()).hexdigest()}\nfiles={len(files)}')

if __name__=='__main__': main()
