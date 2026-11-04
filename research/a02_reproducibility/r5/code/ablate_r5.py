"""Explicitly post-hoc R5 ablations. No primary hypothesis is redefined.

Retrains the *same* frozen seeds solely to reconstruct validation features
and isolate disagreement from probability dispersion under the same learner.
"""
from __future__ import annotations
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss
from run_temporal_co2 import make_co2_task,split_by_calendar,make_model
from r5_core import (train_error_model,predict_error_risk,frozen_threshold,
    frozen_stream_review,batch_exact_review,policy_metrics)


def features(conf,refpred,dis,std,kind):
    u=1-np.asarray(conf,dtype=float)
    base=[u,np.asarray(refpred,dtype=float)]
    if kind in ('confidence_plus_disagreement','full'):
        base+=[np.asarray(dis,dtype=float)]
    if kind in ('confidence_plus_std','full'):
        base+=[np.asarray(std,dtype=float)]
    if kind in ('confidence_plus_disagreement','full'):
        base+=[u*np.asarray(dis,dtype=float)]
    return np.column_stack(base)


def run(protocol,out,main_results):
    p=json.loads(protocol.read_text())
    _,X,y,dates,_=make_co2_task()
    kinds=('confidence_only','confidence_plus_disagreement','confidence_plus_std','full')
    rows=[]
    for fold in p['temporal_folds']:
        tr,va,te=split_by_calendar(dates,fold)
        scaler=StandardScaler().fit(X[tr]);Xt=scaler.transform(X[tr]);V=scaler.transform(X[va]);T=scaler.transform(X[te])
        for family in p['model_families']:
            ref=make_model(family,p['reference_fit_seed']).fit(Xt,y[tr])
            ref_p=[ref.predict_proba(z)[:,1] for z in (V,T)]
            ref_y=[ref.predict(z) for z in (V,T)]
            audit_probs=[[],[]]; audit_cls=[[],[]]
            for s in range(p['auxiliary_fit_seeds']['start'],p['auxiliary_fit_seeds']['stop_exclusive']):
                model=make_model(family,s).fit(Xt,y[tr])
                for j,z in enumerate((V,T)):
                    audit_probs[j].append(model.predict_proba(z)[:,1]);audit_cls[j].append(model.predict(z))
            conf=[];dis=[];std=[]
            for j in range(2):
                conf.append(np.maximum(ref_p[j],1-ref_p[j]))
                dis.append(np.mean(np.column_stack(audit_cls[j])!=ref_y[j][:,None],axis=1))
                std.append(np.std(np.column_stack(audit_probs[j]),axis=1))
            ids=[str(__import__('pandas').Timestamp(z).date()) for z in dates[te]]
            errors_val=(ref_y[0]!=y[va]).astype(int)
            errors_test=(ref_y[1]!=y[te]).astype(int)
            for kind in kinds:
                z1=features(conf[0],ref_y[0],dis[0],std[0],kind)
                z2=features(conf[1],ref_y[1],dis[1],std[1],kind)
                model=train_error_model(z1,errors_val)
                val_score=predict_error_risk(model,z1)
                test_score=predict_error_risk(model,z2)
                t=frozen_threshold(val_score,p['review_budget'])
                for mode, mask in (('stream',frozen_stream_review(test_score,ids,t,55043)),
                    ('batch',batch_exact_review(test_score,ids,p['review_budget'],55043))):
                    m=policy_metrics(y[te],ref_y[1],mask,p['review_cost_lambda'])
                    rows.append({'fold':fold['name'],'model':family,'ablation':kind,'mode':mode,
                        'brier_score':brier_score_loss(errors_test,test_score),**m})
    out.mkdir(parents=True,exist_ok=True)
    path=out/'R5_POSTHOC_ABLATIONS.csv'
    with path.open('w',newline='',encoding='utf-8') as handle:
        w=csv.DictWriter(handle,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Sanity: full-feature model must exactly reproduce each primary policy risk.
    main=[]
    with (main_results/'POLICY_OUTCOMES.csv').open(newline='') as fh:main=list(csv.DictReader(fh))
    for row in rows:
        if row['ablation']!='full':continue
        matches=[z for z in main if z['fold']==row['fold'] and z['model']==row['model'] and z['mode']==row['mode'] and z['policy']=='calibrated_conditional']
        if len(matches)!=1 or abs(float(matches[0]['joint_review_cost'])-float(row['joint_review_cost']))>1e-12:
            raise AssertionError('ablation full does not reproduce primary results')
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--main-results',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(run(a.protocol,a.out,a.main_results))
