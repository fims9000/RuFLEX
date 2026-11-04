"""Frozen-protocol R5 temporal challenge; never selects policies on held-out labels.

This is an exploratory single historical time-series challenge, *not* an
externally preregistered multi-institution confirmation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import brier_score_loss

from r5_core import (risk_features,train_error_model,predict_error_risk,
    frozen_threshold,frozen_stream_review,batch_exact_review,policy_metrics,
    paired_moving_block_ci)

TIE_SEED = 55043  # Frozen in PROTOCOL_R5.json, tie_handling field.

MODEL_PARAMS={
 "logistic_regression":{"max_iter":700,"solver":"lbfgs"},
 "decision_tree":{"min_samples_leaf":2},
 "random_forest":{"n_estimators":20,"max_features":"sqrt","min_samples_leaf":2,"n_jobs":1},
 "sgd_log_loss":{"loss":"log_loss","alpha":.0001,"max_iter":1000,"tol":.001},
}


def make_model(family,seed):
    if family=="logistic_regression":
        return LogisticRegression(random_state=seed,**MODEL_PARAMS[family])
    if family=="decision_tree":
        return DecisionTreeClassifier(random_state=seed,**MODEL_PARAMS[family])
    if family=="random_forest":
        return RandomForestClassifier(random_state=seed,**MODEL_PARAMS[family])
    if family=="sgd_log_loss":
        return SGDClassifier(random_state=seed,**MODEL_PARAMS[family])
    raise ValueError(family)


def make_co2_task():
    original=sm.datasets.co2.load_pandas().data.copy()
    if len(original)!=2284:
        raise RuntimeError("unexpected packaged co2 revision")
    raw=original.co2
    # History-only filling; no backward interpolation or use of future measurement.
    past=raw.ffill()
    index=original.index
    x=pd.DataFrame(index=index)
    x['co2_current']=past
    for lag in (1,2,4,8): x[f'co2_lag{lag}']=past.shift(lag)
    x['delta1']=past-past.shift(1)
    x['delta4']=past-past.shift(4)
    x['past_mean4']=past.rolling(4).mean()
    x['past_mean8']=past.rolling(8).mean()
    day=index.dayofyear.to_numpy()
    x['season_sin']=np.sin(2*np.pi*day/365.2425)
    x['season_cos']=np.cos(2*np.pi*day/365.2425)
    # Label uses original observed measurements, not future-filled/imputed targets.
    usable=raw.notna() & raw.shift(-1).notna() & (~x.isna().any(axis=1))
    X=x.loc[usable]
    y=(raw.shift(-1).loc[usable].to_numpy()>raw.loc[usable].to_numpy()).astype(int)
    if X.columns.tolist()!=['co2_current','co2_lag1','co2_lag2','co2_lag4','co2_lag8',
                             'delta1','delta4','past_mean4','past_mean8','season_sin','season_cos']:
        raise RuntimeError("feature contract mismatch")
    if not np.isfinite(X.to_numpy()).all(): raise RuntimeError("nonfinite features")
    return original,X.to_numpy(),y,X.index.to_numpy(),X.columns.tolist()


def split_by_calendar(dates,fold):
    t=pd.DatetimeIndex(dates)
    train=np.flatnonzero(t<=pd.Timestamp(fold['train_until']))
    val=np.flatnonzero((t>=pd.Timestamp(fold['validation_from'])) & (t<=pd.Timestamp(fold['validation_until'])))
    test=np.flatnonzero((t>=pd.Timestamp(fold['test_from'])) & (t<=pd.Timestamp(fold['test_until'])))
    if min(len(train),len(val),len(test))<50: raise ValueError("insufficient time-block size")
    # Rule from the frozen protocol: at least eight calendar weeks separate the blocks.
    if (t[val[0]]-t[train[-1]]).days<56 or (t[test[0]]-t[val[-1]]).days<56:
        raise ValueError("temporal embargo too short")
    return train,val,test


def case_cost(y,pred,review,lam):
    err=(np.asarray(y)!=np.asarray(pred))
    r=np.asarray(review,dtype=bool)
    return (err & ~r).astype(float)+lam*r.astype(float)


def write_csv(path,rows):
    if not rows:raise ValueError("cannot save empty rows")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf8') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys()))
        w.writeheader();w.writerows(rows)


def run(protocol_path,output):
    raw_protocol=protocol_path.read_bytes();p=json.loads(raw_protocol)
    expected='791ee6dd60c84cf09e02cd01571d14c9f646ae46c45f638bd92565aa98804291'
    if hashlib.sha256(raw_protocol).hexdigest()!=expected:
        raise ValueError("R5 protocol bytes have changed after freeze")
    if p['version']!=1 or p['reference_fit_seed'] in range(p['auxiliary_fit_seeds']['start'],p['auxiliary_fit_seeds']['stop_exclusive']):
        raise ValueError("protocol version or seed conflict")
    original,X,y,dates,features=make_co2_task()
    original_digest=hashlib.sha256(original.to_csv().encode()).hexdigest()
    output.mkdir(parents=True,exist_ok=True)
    summary=[];cases=[];policies=[]
    for fold in p['temporal_folds']:
        train,val,test=split_by_calendar(dates,fold)
        scaler=StandardScaler().fit(X[train])
        fit_x=scaler.transform(X[train]); xv=scaler.transform(X[val]);xt=scaler.transform(X[test])
        for fam in p['model_families']:
            name=f"{fold['name']}::{fam}"
            ref=make_model(fam,p['reference_fit_seed']).fit(fit_x,y[train])
            inputs=[xv,xt]
            refprobs=[ref.predict_proba(z)[:,1] for z in inputs]
            refpred=[ref.predict(z).astype(int) for z in inputs]
            audit_prob=[[],[]];audit_label=[[],[]]
            for seed in range(p['auxiliary_fit_seeds']['start'],p['auxiliary_fit_seeds']['stop_exclusive']):
                model=make_model(fam,seed).fit(fit_x,y[train])
                for j,z in enumerate(inputs):
                    audit_prob[j].append(model.predict_proba(z)[:,1])
                    audit_label[j].append(model.predict(z).astype(int))
            conf=[];dis=[];std=[];score={}
            for j in range(2):
                probs=np.column_stack(audit_prob[j]);labels=np.column_stack(audit_label[j])
                conf.append(np.maximum(refprobs[j],1-refprobs[j]))
                dis.append(np.mean(labels!=refpred[j][:,None],axis=1))
                std.append(np.std(probs,axis=1))
            Xb_val=risk_features(conf[0],refpred[0],dis[0],std[0],augmented=False)
            Xa_val=risk_features(conf[0],refpred[0],dis[0],std[0],augmented=True)
            Xb_test=risk_features(conf[1],refpred[1],dis[1],std[1],augmented=False)
            Xa_test=risk_features(conf[1],refpred[1],dis[1],std[1],augmented=True)
            validation_errors=(refpred[0]!=y[val]).astype(int)
            baseline=train_error_model(Xb_val,validation_errors)
            augmented=train_error_model(Xa_val,validation_errors)
            score_val={
                'confidence_only_raw':1-conf[0],
                'confidence_plus_disagreement_fixed':1-conf[0]+.5*dis[0],
                'calibrated_confidence':predict_error_risk(baseline,Xb_val),
                'calibrated_conditional':predict_error_risk(augmented,Xa_val),
            }
            score_test={
                'confidence_only_raw':1-conf[1],
                'confidence_plus_disagreement_fixed':1-conf[1]+.5*dis[1],
                'calibrated_confidence':predict_error_risk(baseline,Xb_test),
                'calibrated_conditional':predict_error_risk(augmented,Xa_test),
            }
            identity=[str(pd.Timestamp(d).date()) for d in dates[test]]
            all_masks={}
            for policy in p['candidate_risk_rankers']:
                threshold=frozen_threshold(score_val[policy],p['review_budget'])
                stream=frozen_stream_review(score_test[policy],identity,threshold,TIE_SEED)
                batch=batch_exact_review(score_test[policy],identity,p['review_budget'],TIE_SEED)
                all_masks[(policy,'stream')]=stream
                all_masks[(policy,'batch')]=batch
                for mode,mask in [('stream',stream),('batch',batch)]:
                    m=policy_metrics(y[test],refpred[1],mask,p['review_cost_lambda'])
                    summary.append({'fold':fold['name'],'model':fam,'policy':policy,'mode':mode,
                                    'train_n':len(train),'validation_n':len(val),'test_n':len(test),
                                    'review_cost_lambda':p['review_cost_lambda'],
                                    'validation_errors':int(validation_errors.sum()),
                                    'calibration_cutoff':threshold.cutoff,
                                    'calibration_tie_p':threshold.tie_probability,**m})
                    policies.append({'fold':fold['name'],'model':fam,'policy':policy,'mode':mode,
                        'valid_n':int(len(val)),'expected_review_val':threshold.requested_count,
                        'test_review':m['reviewed'],'calibrated_without_test_labels':True})
            # Conditional risk boundary crossings are diagnostic only, not a theorem for fitted risks.
            crossed=((score_test['calibrated_confidence']-p['review_cost_lambda'])*
                     (score_test['calibrated_conditional']-p['review_cost_lambda'])<0)
            base_cost=case_cost(y[test],refpred[1],all_masks[('calibrated_confidence','stream')],p['review_cost_lambda'])
            augmented_cost=case_cost(y[test],refpred[1],all_masks[('calibrated_conditional','stream')],p['review_cost_lambda'])
            ci=paired_moving_block_ci(augmented_cost-base_cost,
                 block_length=min(p['bootstrap']['block_size_weeks'],len(test)),
                 replicates=p['bootstrap']['replicates'],seed=p['bootstrap']['seed'])
            has_clf_err=(refpred[1]!=y[test]).astype(int)
            base_brier=float(brier_score_loss(has_clf_err,score_test['calibrated_confidence']))
            augmented_brier=float(brier_score_loss(has_clf_err,score_test['calibrated_conditional']))
            high=(conf[1]>=.9)
            high_stable=high & (dis[1]==0)
            report={'cell':name,'fold':fold['name'],'model':fam,'test_n':len(test),
                'validation_error_count':int(validation_errors.sum()),
                'test_reference_errors':int(has_clf_err.sum()),
                'crossing_n':int(crossed.sum()),'crossing_fraction':float(crossed.mean()),
                'conditional_error_brier':augmented_brier,'confidence_error_brier':base_brier,
                'brier_delta':augmented_brier-base_brier,
                'stream_cost_delta':float(np.mean(augmented_cost-base_cost)),
                'stream_cost_moving_block_ci_low':ci[0],
                'stream_cost_moving_block_ci_high':ci[1],
                'high_confidence_count':int(high.sum()),
                'high_confidence_stable_count':int(high_stable.sum()),
                'high_confidence_stable_wrong_n':int((high_stable & (has_clf_err==1)).sum()),
            }
            for i,idx in enumerate(test):
                row={'cell':name,'fold':fold['name'],'model':fam,'date':identity[i],
                    'truth':int(y[idx]),'reference_prediction':int(refpred[1][i]),
                    'reference_confidence':float(conf[1][i]),
                    'reference_disagreement':float(dis[1][i]),
                    'reference_probability_std':float(std[1][i]),
                    'reference_is_wrong':int(has_clf_err[i])}
                row.update({f'risk_{k}':float(v[i]) for k,v in score_test.items()})
                row.update({f'review_{policy}_{mode}':int(mask[i]) for (policy,mode),mask in all_masks.items()})
                cases.append(row)
            print('FINISHED',name,'delta_cost',round(report['stream_cost_delta'],6),
                  'cross',report['crossing_n'],'brier_delta',round(report['brier_delta'],5),flush=True)
            output.joinpath('cell_'+name.replace(':','_')+'.json').write_text(json.dumps(report,indent=2)+'\n')
    write_csv(output/'POLICY_OUTCOMES.csv',summary)
    write_csv(output/'CASE_LEVEL_TEMPORAL.csv',cases)
    write_csv(output/'FROZEN_THRESHOLDS.csv',policies)
    source={
        'protocol_sha256':expected,'dataset_sha256':original_digest,
        'reference_and_audit_fit_count':len(p['temporal_folds'])*len(p['model_families'])*(1+p['auxiliary_fit_seeds']['stop_exclusive']-p['auxiliary_fit_seeds']['start']),
        'cells':len(p['temporal_folds'])*len(p['model_families']),
        'primary_fold':'late_primary','exploratory_temporal_challenge':True,
        'test_labels_not_used_for_scoring':True,
        'data_from_statsmodels':sm.__version__,
        'source_feature_list':features,
        'review_policy':p['candidate_risk_rankers'],
        'files_sha256':{}
    }
    for f in ('POLICY_OUTCOMES.csv','CASE_LEVEL_TEMPORAL.csv','FROZEN_THRESHOLDS.csv'):
        source['files_sha256'][f]=hashlib.sha256((output/f).read_bytes()).hexdigest()
    (output/'R5_TEMPORAL_RECEIPT.json').write_text(json.dumps(source,indent=2)+'\n')
    print('TOTAL',source['reference_and_audit_fit_count'],'fits,',source['cells'],'cells',flush=True)
    return source


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--protocol',type=Path,required=True)
    pa.add_argument('--out',type=Path,required=True)
    args=pa.parse_args()
    run(args.protocol,args.out)
if __name__=='__main__':main()
