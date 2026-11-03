"""Read-only A05 verifier: exact Beta bounds and recorded seeded-fit sample design."""
from pathlib import Path
from collections import defaultdict
import csv,hashlib,json,math
import numpy as np
from scipy.stats import beta
ROOT=Path(__file__).parents[1];protocol=ROOT/'code'/'a05_protocol.json';r=ROOT/'results'/'a05_certification'
p=json.loads(protocol.read_text());m=json.loads((r/'A05_MANIFEST.json').read_text())
assert m['protocol_sha256']==hashlib.sha256(protocol.read_bytes()).hexdigest()
for fn,sha in m['files_sha256'].items():assert hashlib.sha256((r/fn).read_bytes()).hexdigest()==sha
with (r/'A05_CASE_LEVEL.csv').open() as f:cases=list(csv.DictReader(f))
with (r/'A05_CELLS.csv').open() as f:cells=list(csv.DictReader(f))
seeds=json.loads((r/'A05_SEEDS.json').read_text())
lookup={(v['dataset'],v['model_family'],int(v['split_seed'])):v for v in cells}
g=defaultdict(list)
for row in cases:
 key=(row['dataset'],row['model_family'],int(row['split_seed']))
 g[key].append(row)
 assert int(row['error'])==(int(row['reference_label'])!=int(row['truth']))
 assert int(row['n_audit'])==p['audit_fits_per_cell']
 k=int(row['successes']);n=int(row['n_audit']);alpha=p['alpha']/int(lookup[key]['n_test'])
 expected=float(beta.ppf(alpha,k,n-k+1)) if k>0 else 0.0
 assert math.isclose(float(row['bonferroni_lower']),expected,abs_tol=1e-12)
 assert int(row['certified'])==(expected>=p['target'])
 assert math.isclose(float(row['observed_agreement']),k/n,abs_tol=1e-12)
assert len(g)==len(cells)==len(seeds)==40
for key,group in g.items():
 meta=lookup[key];assert len(group)==int(meta['n_test'])
 assert sum(int(x['certified']) for x in group)==int(meta['n_certified'])
 assert sum(int(x['error']) for x in group)==int(meta['test_errors'])
 assert sum(int(x['certified'])*int(x['error']) for x in group)==int(meta['certified_wrong'])
for ss in seeds:
 assert len(ss['draws'])==p['audit_fits_per_cell']
 assert p['reference_seed'] not in ss['draws']
 assert ss['distinct_seed_count']==len(set(ss['draws']))
print(json.dumps({'cells_verified':len(cells),'case_level_certificates':len(cases),'status':'PASS','certified_total':m['certified_case_cells'],'certified_wrong':m['certified_wrong_case_cells']},indent=2))
