#!/usr/bin/env python3
"""Static sanity checks for the packaged technical specification."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'02_RuFLEX_FULL_TECHNICAL_SPEC_v1.md'
t=p.read_text(encoding='utf-8')
ids=re.findall(r'^## \[((?:P0|P1|P2)-\d+)\]\s+',t,re.M)
required=[f'P0-{i:02d}' for i in range(1,21)]
miss=[x for x in required if x not in ids]
dup=sorted({x for x in ids if ids.count(x)>1})
print('module sections:',len(ids))
print('P0 sections:',sum(x.startswith('P0-') for x in ids))
if miss: print('missing P0:',miss)
if dup: print('duplicate IDs:',dup)
if miss or dup: raise SystemExit(1)
print('PASS')
