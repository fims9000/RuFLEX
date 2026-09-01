#!/usr/bin/env python3
"""Print one RuFLEX module specification to stdout.

Usage:
  python scripts/extract_module.py P0-01
  python scripts/extract_module.py P1-03 --spec path/to/spec.md
"""
from __future__ import annotations
import argparse, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / '02_RuFLEX_FULL_TECHNICAL_SPEC_v1.md'


def extract(text: str, module_id: str) -> str:
    pat = re.compile(rf'^## \[{re.escape(module_id)}\]\s+.*$', re.M)
    m = pat.search(text)
    if not m:
        raise KeyError(module_id)
    next_m = re.search(r'^## \[(?:P0|P1|P2)-\d+\]\s+.*$', text[m.end():], re.M)
    end = m.end() + (next_m.start() if next_m else len(text[m.end():]))
    return text[m.start():end].rstrip() + '\n'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('module_id')
    ap.add_argument('--spec', type=Path, default=DEFAULT_SPEC)
    args = ap.parse_args()
    text = args.spec.read_text(encoding='utf-8')
    try:
        print(extract(text, args.module_id), end='')
    except KeyError:
        print(f'ERROR: module {args.module_id!r} not found in {args.spec}', file=__import__('sys').stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
