"""A05: fixed-reference held-out certification with pseudo-randomly sampled audit seeds."""
from __future__ import annotations
import csv,hashlib,json,math,time
from pathlib import Path
import numpy as np
from scipy.stats import beta
from a03_heldout import data_regimes,model,split,save_rows


def execute(protocol_path,out):
    p=json.loads(Path(protocol_path).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=True)
    hh=hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest()
    (out/'START_RECEIPT.json').write_text(json.dumps({'protocol_sha256':hh,'status':'RUN_STARTED'},indent=2))
    cases=[];cells=[];seed_records=[]
    t0=time.monotonic()
    for split_seed in p['split_seeds']:
      for name,x,y,kind in data_regimes():
        if name not in p['datasets']:continue
        xtr,ytr,xv,yv,xt,yt,vi,ti,tr=split(x,y,split_seed)
        for fam in p['models']:
            reference=model(fam,p['reference_seed']).fit(xtr,ytr)
            ref_label=reference.predict(xt)
            ref_conf=np.max(reference.predict_proba(xt),axis=1)
            source=f'{split_seed}:{name}:{fam}:{p["master_seed"]}'
            cell_master=int(hashlib.sha256(source.encode()).hexdigest()[:16],16)
            rng=np.random.default_rng(cell_master)
            seeds=[]
            while len(seeds)<p['audit_fits_per_cell']:
                seed=int(rng.integers(0,2**31))
                if seed!=p['reference_seed']:seeds.append(seed)
            seen=np.zeros(len(yt),dtype=int)
            for seed in seeds:
                fit=model(fam,seed).fit(xtr,ytr)
                seen+=(fit.predict(xt)==ref_label)
            k=seen;n=p['audit_fits_per_cell'];m=len(yt)
            lower=np.where(k==0,0.0,beta.ppf(p['alpha']/m,k,n-k+1))
            yes=(lower>=p['target'])
            for j,caseid in enumerate(ti):
                cases.append(dict(split_seed=split_seed,dataset=name,model_family=fam,
                  cell_key=f'{name}::{fam}::split{split_seed}',case_id=int(caseid),
                  truth=int(yt[j]),reference_label=int(ref_label[j]),
                  error=int(ref_label[j]!=yt[j]),confidence=float(ref_conf[j]),
                  successes=int(k[j]),n_audit=n,
                  observed_agreement=float(k[j]/n),bonferroni_lower=float(lower[j]),
                  certified=int(yes[j])))
            cells.append(dict(split_seed=split_seed,dataset=name,model_family=fam,
              n_test=m,n_certified=int(yes.sum()),certified_fraction=float(yes.mean()),
              certified_wrong=int(np.sum(yes&(yt!=ref_label))),
              uncertified_wrong=int(np.sum(~yes&(yt!=ref_label))),
              test_errors=int(np.sum(ref_label!=yt)),
              high_conf_instability=int(np.sum((ref_conf>=.9)&(k/n<.8)))))
            seed_records.append({'cell_key':f'{name}::{fam}::split{split_seed}',
              'draws':seeds,'master':cell_master,
              'sampled_with_replacement':True,'distinct_seed_count':len(set(seeds))})
            print(f'{len(cells):2d} {name:28s} {fam:20s} split={split_seed} '
                  f'cert={yes.sum()}/{m} bad_cert={int(np.sum(yes&(yt!=ref_label)))}',flush=True)
            save_rows(out/'A05_CASE_LEVEL.csv',cases)
            save_rows(out/'A05_CELLS.csv',cells)
    (out/'A05_SEEDS.json').write_text(json.dumps(seed_records,indent=2)+'\n')
    manifest={'protocol_sha256':hh,'cells':len(cells),
      'fits':len(cells)*(p['audit_fits_per_cell']+1),'test_case_cells':len(cases),
      'certified_case_cells':sum(x['n_certified'] for x in cells),
      'certified_wrong_case_cells':sum(x['certified_wrong'] for x in cells),
      'runtime_s':round(time.monotonic()-t0,2),
      'files_sha256':{f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in
       ('A05_CASE_LEVEL.csv','A05_CELLS.csv','A05_SEEDS.json')}}
    (out/'A05_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
 import argparse
 pa=argparse.ArgumentParser();pa.add_argument('--protocol',type=Path,default=Path(__file__).parent/'a05_protocol.json');pa.add_argument('--out',type=Path,required=True);args=pa.parse_args()
 print(json.dumps(execute(args.protocol,args.out),indent=2))
