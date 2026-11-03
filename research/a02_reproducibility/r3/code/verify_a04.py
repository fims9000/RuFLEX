"""Independent A04 ablation verification against A03 saved held-out evidence."""
from pathlib import Path
import csv,hashlib,json,math
import numpy as np
from collections import defaultdict

ROOT=Path(__file__).parents[1]
a04=ROOT/'results'/'a04_budget'
m=json.loads((a04/'A04_MANIFEST.json').read_text())
assert hashlib.sha256((a04/'A04_CHECKPOINTS.csv').read_bytes()).hexdigest()==m['checkpoint_table_sha256']
with (a04/'A04_CHECKPOINTS.csv').open() as f: rows=list(csv.DictReader(f))
assert len(rows)==32*4
bycell=defaultdict(list)
for r in rows: bycell[r['cell_key']].append(r)
for cell,rs in bycell.items():
    dataset,model,part=cell.split('::'); seed=int(part.removeprefix('split'))
    p=a04/'predictions'/f'{dataset}__{model}__split{seed}.npz'
    sha=next(x['prediction_sha256'] for x in m['cell_artifacts'] if x['cell_key']==cell)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
    with np.load(p) as f: data={k:f[k] for k in f.files}
    ref=data['ref_prediction'];conf=data['ref_confidence'];truth=data['truth'];ids=data['case_ids'];aux=data['aux_predictions']
    assert aux.shape==(30,len(ref))
    assert len(np.unique(ids))==len(ids)
    a03_path=ROOT/'results'/f'split{seed}'/'A03_CASE_LEVEL.csv'
    with open(a03_path) as fh:
        a03={int(r['case_id']):r for r in csv.DictReader(fh) if r['cell_key']==cell and r['partition']=='heldout'}
    assert set(ids)==set(a03)
    for j,i in enumerate(ids):
        x=a03[int(i)]
        assert int(x['truth'])==truth[j] and int(x['reference_prediction'])==ref[j]
        assert abs(float(x['ref_confidence'])-conf[j])<1e-9
        assert abs(float(x['observed_agreement'])-np.mean(aux[:,j]==ref[j]))<1e-9
    for r in rs:
        n=int(r['n_audit_fits']);scores=(1-conf)+.5*(aux[:n]==ref).mean(axis=0)*0 # overwritten below
        scores=(1-conf)+.5*(1-(aux[:n]==ref).mean(axis=0))
        # independent tie sort
        def h(x):return int(hashlib.sha256(f'0:{x}'.encode()).hexdigest()[:16],16)
        k=math.ceil(.1*len(ids)-1e-12)
        order=sorted(range(len(ids)),key=lambda j:(-float(scores[j]),h(int(ids[j]))))
        rejected=set(order[:k])
        risk=sum(int(ref[j]!=truth[j]) for j in range(len(ids)) if j not in rejected)/(len(ids)-k)
        assert abs(risk-float(r['accepted_risk']))<1e-12,(cell,n)
        if n==30:
            with open(ROOT/'results'/f'split{seed}'/'A03_POLICY_OUTCOMES.csv') as fh:
                master=next(t for t in csv.DictReader(fh) if t['cell_key']==cell and t['policy']=='combined_fixed' and float(t['budget'])==.9)
            assert abs(float(master['accepted_risk'])-risk)<1e-12
print(json.dumps({'cells':len(bycell),'checkpoints':len(rows),'status':'independent A04 replay and A03 30-fit agreement PASS'},indent=2))
