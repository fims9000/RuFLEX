#!/usr/bin/env python3
"""Mechanical RuFLEX module receipt verifier.

This script checks evidence *presence and integrity*, not scientific truth.
It intentionally cannot declare a model correct or a research claim true.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / '02_RuFLEX_FULL_TECHNICAL_SPEC_v1.md'

REQUIRED = {
    'module_id', 'spec_version', 'code_ref', 'tests', 'acceptance',
    'artifacts', 'protocol_deviations', 'known_limitations', 'status'
}


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--module', required=True)
    ap.add_argument('--receipt', type=Path)
    ap.add_argument('--allow-worktree', action='store_true', help='allow code_ref=WORKTREE for development verification')
    args = ap.parse_args()
    mid = args.module

    spec_text = SPEC.read_text(encoding='utf-8')
    if not re.search(rf'^## \[{re.escape(mid)}\]\s+', spec_text, re.M):
        print(f'FAIL: {mid} is not present in the technical specification')
        return 2

    receipt = args.receipt or ROOT / 'records' / 'modules' / mid / 'receipt.json'
    if not receipt.exists():
        print(f'FAIL: missing receipt {receipt}')
        return 2

    try:
        r = load(receipt)
    except Exception as e:
        print(f'FAIL: invalid receipt JSON: {e}')
        return 2

    missing = REQUIRED - set(r)
    errors=[]
    if missing:
        errors.append(f'missing fields: {sorted(missing)}')
    if r.get('module_id') != mid:
        errors.append('module_id mismatch')
    if r.get('status') != 'VERIFIED':
        errors.append(f"receipt status is {r.get('status')!r}, expected 'VERIFIED'")
    if not r.get('tests'):
        errors.append('no tests recorded')
    else:
        failed=[x for x in r['tests'] if x.get('status')!='PASS']
        if failed:
            errors.append(f'{len(failed)} recorded tests are not PASS')
    if not r.get('acceptance'):
        errors.append('no acceptance criteria recorded')
    else:
        incomplete=[x for x in r['acceptance'] if x.get('status')!='PASS']
        if incomplete:
            errors.append(f'{len(incomplete)} acceptance criteria are not PASS')
    code_ref=r.get('code_ref')
    if not code_ref:
        errors.append('empty code_ref')
    if code_ref == 'WORKTREE' and not args.allow_worktree:
        errors.append('code_ref is WORKTREE; pass --allow-worktree only during development')

    # Validate artifact paths only when a path is supplied. External/content-addressed refs may be non-path IDs.
    for a in r.get('artifacts', []):
        if isinstance(a, dict) and a.get('path'):
            p=(ROOT / a['path']).resolve() if not Path(a['path']).is_absolute() else Path(a['path'])
            if not p.exists():
                errors.append(f"artifact path missing: {a['path']}")

    if errors:
        print('FAIL')
        for e in errors:
            print(' -',e)
        print('NOTE: this verifier only checks the receipt/evidence contract; passing it does not establish scientific validity.')
        return 1

    print(f'PASS: {mid} receipt is mechanically complete.')
    print('NOTE: scientific validity still requires the module-specific evidence/reviewer checks in the TZ.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
