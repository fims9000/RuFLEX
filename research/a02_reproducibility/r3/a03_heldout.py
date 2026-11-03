"""A03: reproducibility-aware held-out selective review at exactly matched budgets.

Research-only; every candidate policy and all split/seed choices are fixed by
``a03_protocol.json``. A01/A02 artifacts are neither read nor altered.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.datasets import load_iris, load_wine, load_digits, load_breast_cancer, make_classification
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

POLICIES = ('confidence_only', 'disagreement_only', 'combined_fixed', 'dispersion_fixed')


def data_regimes():
    iris = load_iris(); wine = load_wine(); digits = load_digits(); cancer = load_breast_cancer()
    bundles = [
        ('iris_virginica', iris.data, (iris.target == 2).astype(int), 'public_bundled'),
        ('wine_class0', wine.data, (wine.target == 0).astype(int), 'public_bundled'),
        ('digits_5_to_9', digits.data, (digits.target >= 5).astype(int), 'public_bundled'),
        ('breast_cancer_malignant', cancer.data, (cancer.target == 0).astype(int), 'public_bundled'),
    ]
    for sep in (0.5, 1.5):
        for flip in (0.01, 0.15):
            x, y = make_classification(n_samples=1000, n_features=20, n_informative=5,
              n_redundant=3, weights=[0.75, 0.25], class_sep=sep, flip_y=flip, random_state=20260923)
            bundles.append((f'synthetic_sep{sep}_noise{flip}', x, y, 'synthetic_shared_generator'))
    return [(name, np.asarray(x, dtype=np.float64), np.asarray(y, dtype=int), kind) for name, x, y, kind in bundles]


def model(name: str, seed: int):
    from sklearn.tree import DecisionTreeClassifier
    if name == 'logistic_regression': return LogisticRegression(max_iter=1000,solver='lbfgs',random_state=seed)
    if name == 'decision_tree': return DecisionTreeClassifier(random_state=seed)
    if name == 'random_forest': return RandomForestClassifier(n_estimators=25,max_features='sqrt',n_jobs=1,random_state=seed)
    if name == 'extra_trees': return ExtraTreesClassifier(n_estimators=25,max_features='sqrt',n_jobs=1,random_state=seed)
    if name == 'sgd_log_loss': return SGDClassifier(loss='log_loss',alpha=.0001,max_iter=1000,tol=1e-3,random_state=seed)
    raise ValueError(name)


def split(x, y, seed):
    ids = np.arange(y.size)
    train, other = train_test_split(ids,train_size=.6,random_state=seed,stratify=y)
    val, test = train_test_split(other,train_size=.5,random_state=seed+1,stratify=y[other])
    assert not set(train)&set(val) and not set(val)&set(test) and not set(train)&set(test)
    transform = StandardScaler().fit(x[train])
    return transform.transform(x[train]), y[train], transform.transform(x[val]), y[val], transform.transform(x[test]),y[test],val,test,train


def scores(confidence: np.ndarray, agreement: np.ndarray, probability_std: np.ndarray):
    uncertainty = 1 - confidence
    disagreement = 1 - agreement
    return {'confidence_only':uncertainty,
            'disagreement_only':disagreement,
            'combined_fixed':uncertainty+.5*disagreement,
            'dispersion_fixed':uncertainty+.5*probability_std}


def tie_hash(case_id: int, tie_seed: int) -> int:
    # Completely independent of ground-truth labels; do not use Python hash salt.
    return int(hashlib.sha256(f'{tie_seed}:{case_id}'.encode('ascii')).hexdigest()[:16],16)


def review_mask(s: np.ndarray, case_ids: np.ndarray, coverage: float, tie_seed: int=0):
    """Exact review count from unlabeled scores, with unbiased reproducible ties."""
    n=len(s)
    if not 0 < coverage < 1 or n==0 or len(case_ids)!=n or np.any(~np.isfinite(s)):
        raise ValueError('invalid score, length or target budget')
    k=math.ceil((1-coverage)*n-1e-12)
    order=sorted(range(n),key=lambda i:(-float(s[i]),tie_hash(int(case_ids[i]),tie_seed)))
    mask=np.zeros(n,dtype=bool); mask[order[:k]]=True
    return mask


def assess(y, prediction, reject):
    keep=~reject
    errors=(prediction!=y)
    retained=int(keep.sum())
    total_errors=int(errors.sum())
    return dict(n=len(y),n_review=int(reject.sum()),coverage=float(keep.mean()),
                n_accepted=retained,accepted_errors=int((errors&keep).sum()),
                accepted_risk=float((errors&keep).sum()/retained) if retained else None,
                reviewed_errors=int((errors&reject).sum()),
                recall_of_errors_reviewed=float((errors&reject).sum()/total_errors) if total_errors else None,
                error_count=total_errors,reference_accuracy=float((~errors).mean()))


def bootstrap_delta(y,pred,left_reject,right_reject, seed, reps=2000):
    """Fixed selection policies: per-case paired percentile bootstrap; no reselection."""
    err=(pred!=y).astype(np.float64)
    a=(~left_reject).astype(np.float64); b=(~right_reject).astype(np.float64)
    rng=np.random.default_rng(seed)
    idx=rng.integers(0,len(y),size=(reps,len(y)))
    n_a=a[idx].sum(axis=1); n_b=b[idx].sum(axis=1)
    valid=(n_a>0)&(n_b>0)
    if valid.mean()<.9:
        return {'delta_ci95':None,'valid_replicates':int(valid.sum()),'reason':'too_few_valid_replicates'}
    left=(err[idx]*a[idx]).sum(axis=1)[valid]/n_a[valid]
    right=(err[idx]*b[idx]).sum(axis=1)[valid]/n_b[valid]
    delta=left-right
    return {'delta_ci95':[float(v) for v in np.percentile(delta,[2.5,97.5])],
            'valid_replicates':int(valid.sum()),'reason':None}


def execute(protocol_path: Path,out_dir: Path,*,only_split: int|None=None):
    protocol_bytes=protocol_path.read_bytes()
    p=json.loads(protocol_bytes)
    if p['version']!=1: raise ValueError('invalid protocol')
    if p['reference_seed'] in range(p['audit_seed_start'],p['audit_seed_start']+p['audit_seed_count']):
        raise ValueError('reference overlaps audit fits')
    os.makedirs(out_dir,exist_ok=True)
    proof={'protocol_sha256':hashlib.sha256(protocol_bytes).hexdigest(),'protocol':p['protocol'],
           'frozen_before_labels':True,'n_requested_cells':len(p['split_seeds'])*len(data_regimes())*len(p['model_families'])}
    (out_dir/'START_RECEIPT.json').write_text(json.dumps(proof,indent=2)+'\n')
    sums=[]; details=[]; tie_rows=[]; cell_index=0
    t0=time.monotonic()
    for split_seed in p['split_seeds']:
        if only_split is not None and split_seed!=only_split: continue
        for name,x,y,kind in data_regimes():
            xtr,ytr,xval,yval,xtst,ytst,val_ids,test_ids,train_ids=split(x,y,split_seed)
            for family in p['model_families']:
                started=time.monotonic();cell_index+=1
                fixed=model(family,p['reference_seed']).fit(xtr,ytr)
                yp_val=fixed.predict(xval); yp_test=fixed.predict(xtst)
                pr_val=fixed.predict_proba(xval)[:,1];pr_test=fixed.predict_proba(xtst)[:,1]
                matches_val=np.zeros(len(yval),dtype=np.int32)
                matches_test=np.zeros(len(ytst),dtype=np.int32)
                prob_val=[];prob_test=[]
                for seed in range(p['audit_seed_start'],p['audit_seed_start']+p['audit_seed_count']):
                    aux=model(family,seed).fit(xtr,ytr)
                    v=aux.predict(xval);t=aux.predict(xtst)
                    matches_val+=(v==yp_val);matches_test+=(t==yp_test)
                    prob_val.append(aux.predict_proba(xval)[:,1]);prob_test.append(aux.predict_proba(xtst)[:,1])
                n=p['audit_seed_count'];
                conf_val=np.maximum(pr_val,1-pr_val);conf_test=np.maximum(pr_test,1-pr_test)
                agreement_val=matches_val/n;agreement_test=matches_test/n
                sd_val=np.std(prob_val,axis=0);sd_test=np.std(prob_test,axis=0)
                s_val=scores(conf_val,agreement_val,sd_val);s_test=scores(conf_test,agreement_test,sd_test)
                cell_key=f'{name}::{family}::split{split_seed}'
                for block,ids,ytrue,yp,conf,agreement,sd,sc in [
                  ('validation',val_ids,yval,yp_val,conf_val,agreement_val,sd_val,s_val),
                  ('heldout',test_ids,ytst,yp_test,conf_test,agreement_test,sd_test,s_test)]:
                    for i,case_id in enumerate(ids):
                        details.append(dict(cell_key=cell_key,split_seed=split_seed,source=kind,
                          dataset=name,model_family=family,partition=block,case_id=int(case_id),
                          truth=int(ytrue[i]),reference_prediction=int(yp[i]),
                          ref_confidence=float(conf[i]),observed_agreement=float(agreement[i]),
                          prob_std=float(sd[i]),n_audit=n,reference_error=int(ytrue[i]!=yp[i]),
                          **{f'score_{k}':float(v[i]) for k,v in sc.items()}))
                for budget in p['budgets']:
                    policies={pol:review_mask(sc,test_ids,budget,0) for pol,sc in s_test.items()}
                    baseline=assess(ytst,yp_test,policies['confidence_only'])
                    for policy,rej in policies.items():
                        outcome=assess(ytst,yp_test,rej)
                        boot={'delta_ci95':None,'valid_replicates':None,'reason':'baseline_or_not_primary_budget'}
                        if budget==p['primary_budget'] and policy!='confidence_only':
                            boot=bootstrap_delta(ytst,yp_test,rej,policies['confidence_only'],
                                                 pseed(p['inference'],split_seed,name,family,policy))
                        row=dict(cell_key=cell_key,split_seed=split_seed,dataset=name,kind=kind,
                          model_family=family,budget=budget,policy=policy,
                          n_train=len(ytr),n_validation=len(yval),n_test=len(ytst),
                          n_aux_fits=n,reference_seed=p['reference_seed'],
                          high_conf_unstable_val=int(((conf_val>=.9)&(agreement_val<.8)).sum()),
                          high_conf_unstable_test=int(((conf_test>=.9)&(agreement_test<.8)).sum()),
                          high_conf_count_test=int((conf_test>=.9).sum()),
                          **outcome,delta_risk_vs_confidence=outcome['accepted_risk']-baseline['accepted_risk'],
                          **boot,elapsed_cell_seconds=round(time.monotonic()-started,4))
                        sums.append(row)
                    if budget == p['primary_budget']:
                        for ti in p['tie_sensitivity_seeds']:
                            cp=review_mask(s_test['confidence_only'],test_ids,budget,ti)
                            base_risk=assess(ytst,yp_test,cp)['accepted_risk']
                            for policy in POLICIES:
                                pp=review_mask(s_test[policy],test_ids,budget,ti)
                                out=assess(ytst,yp_test,pp)
                                tie_rows.append(dict(cell_key=cell_key,split_seed=split_seed,
                                  dataset=name,model_family=family,budget=budget,
                                  tie_seed=ti,policy=policy,accepted_risk=out['accepted_risk'],
                                  delta_risk_vs_confidence=out['accepted_risk']-base_risk))
                print(f'{cell_index:3d} split={split_seed} {name:32s} {family:20s} '
                    f'test={len(ytst):3d} HCIR={int(((conf_test>=.9)&(agreement_test<.8)).sum()):3d} '
                    f'elapsed={time.monotonic()-started:.2f}s',flush=True)
                # Save all partial evidence after each cell; external termination does not erase it.
                save_rows(out_dir/'A03_POLICY_OUTCOMES.csv',sums)
                save_rows(out_dir/'A03_CASE_LEVEL.csv',details)
                save_rows(out_dir/'A03_TIE_SENSITIVITY.csv',tie_rows)
    receipt={**proof,'n_completed_cells':cell_index,'n_trainings':cell_index*(p['audit_seed_count']+1),
      'n_case_records':len(details),'n_policy_records':len(sums),'elapsed_s':round(time.monotonic()-t0,3),
      'files_sha256':{f:hashlib.sha256((out_dir/f).read_bytes()).hexdigest() for f in
       ('A03_POLICY_OUTCOMES.csv','A03_CASE_LEVEL.csv','A03_TIE_SENSITIVITY.csv')}}
    (out_dir/'A03_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def save_rows(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def pseed(config, split_seed, name, family,policy):
    raw=f"20261104:{split_seed}:{name}:{family}:{policy}".encode('ascii')
    return int(hashlib.sha256(raw).hexdigest()[:8],16)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--protocol',type=Path,default=Path(__file__).parent/'a03_protocol.json')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--only-split',type=int,default=None)
    args=parser.parse_args()
    print(json.dumps(execute(args.protocol,args.out,only_split=args.only_split),indent=2))

if __name__=='__main__':main()