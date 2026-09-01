#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TPL=ROOT/'templates'/'MODULE_RECEIPT.json'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('module_id')
    args=ap.parse_args()
    dest=ROOT/'records'/'modules'/args.module_id/'receipt.json'
    if dest.exists():
        raise SystemExit(f'exists: {dest}')
    obj=json.loads(TPL.read_text(encoding='utf-8'))
    obj['module_id']=args.module_id
    obj['timestamp_utc']=datetime.now(timezone.utc).isoformat()
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(dest)

if __name__=='__main__':
    main()
