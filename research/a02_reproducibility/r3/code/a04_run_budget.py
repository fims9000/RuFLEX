"""Post-hoc A04 fresh-fit budget sensitivity on two A03 model families.

This ablation reuses previously inspected A03 test splits and MUST NOT be
presented as confirmatory evidence. No threshold/weight tuning is permitted.
"""
from __future__ import annotations
import argparse,csv,json,hashlib,time
from pathlib import Path
import numpy as np
from a03_heldout import data_regimes,model,split,review_mask,assess,save_rows

CHECKPOINTS=(5,10,20,30)
FAMILIES=('decision_tree','sgd_log_loss')
SPLITS=(101,202)
REFERENCE=30000
AUDIT_START=31000
BUDGET=.9


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'predictions').mkdir(exist_ok=True)
    t0=time.monotonic();rows=[];cells=[]
    for split_seed in SPLITS:
      for dataset,x,y,kind in data_regimes():
        xtr,ytr,xval,yval,xtest,ytest,vi,ti,tr=split(x,y,split_seed)
        for family in FAMILIES:
          t_start=time.monotonic()
          ref=model(family,REFERENCE).fit(xtr,ytr)
          reference_pred=ref.predict(xtest)
          reference_conf=np.max(ref.predict_proba(xtest),axis=1)
          calibration=[]
          for seed in range(AUDIT_START,AUDIT_START+max(CHECKPOINTS)):
            fit=model(family,seed).fit(xtr,ytr)
            calibration.append(fit.predict(xtest).astype(np.int8))
          calibration=np.stack(calibration)
          cell=f'{dataset}::{family}::split{split_seed}'
          cp=review_mask(1-reference_conf,ti,BUDGET,0)
          base=assess(ytest,reference_pred,cp)
          data={'ref_prediction':reference_pred,'ref_confidence':reference_conf,
                'truth':ytest,'case_ids':ti,'aux_predictions':calibration}
          target=out/'predictions'/f'{dataset}__{family}__split{split_seed}.npz'
          np.savez_compressed(target,**data)
          for n in CHECKPOINTS:
            agree=np.mean(calibration[:n]==reference_pred,axis=0)
            score=(1-reference_conf)+.5*(1-agree)
            reject=review_mask(score,ti,BUDGET,0)
            outcome=assess(ytest,reference_pred,reject)
            rows.append({'cell_key':cell,'dataset':dataset,'model_family':family,
             'split_seed':split_seed,'n_audit_fits':n,'heldout_n':len(ti),
             'accepted_errors':outcome['accepted_errors'],
             'accepted_risk':outcome['accepted_risk'],
             'confidence_accepted_risk':base['accepted_risk'],
             'delta_risk_vs_confidence':outcome['accepted_risk']-base['accepted_risk'],
             'reviewed_errors':outcome['reviewed_errors'],
             'reference_errors_total':outcome['error_count'],
             'exact_review_n':outcome['n_review']})
          cells.append({'cell_key':cell,'prediction_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                        'duration_s':round(time.monotonic()-t_start,3)})
          print(cell,'checkpoint deltas:',[(q['n_audit_fits'],round(q['delta_risk_vs_confidence'],4)) for q in rows[-4:]],flush=True)
          save_rows(out/'A04_CHECKPOINTS.csv',rows)
    result={'purpose':'post-hoc audit budget ablation, not confirmatory','cells':len(cells),
     'model_fits':len(cells)*(1+max(CHECKPOINTS)),'splits':list(SPLITS),'models':list(FAMILIES),
     'seed_budgets':list(CHECKPOINTS),'coverage':BUDGET,
     'elapsed_s':round(time.monotonic()-t0,2),'cell_artifacts':cells,
     'checkpoint_table_sha256':hashlib.sha256((out/'A04_CHECKPOINTS.csv').read_bytes()).hexdigest()}
    (out/'A04_MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    print(json.dumps(run(args.out),indent=2))
