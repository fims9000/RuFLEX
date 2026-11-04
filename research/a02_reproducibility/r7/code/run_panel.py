"""R7 frozen cross-country temporal panel evaluation.

Official statsmodels World Bank fertility data are bundled with statsmodels,
no download. Country-code filtering uses the local ISO3166 alpha3 registry.

Per-country trajectories are *not* IID, nor are same-year countries independent.
The annual betting process is conditional-mean evidence only; it does not
certify that a future unobserved time block is safe.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry
from statsmodels import datasets
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from evidence import (choose_threshold,review_masks,policy_gain,method_cost,
                      mixture_path,first_evidence_time)

COLUMNS=['level','lag1','lag2','lag3','lag5','diff1','diff3','mean3','time_year']
MODELS=['logistic_regression','decision_tree','random_forest','extra_trees']
STAGES=['train','risk_fit','review_threshold_calibration','labelled_target_monitoring','frozen_future_evaluation']

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def make_panel(protocol):
    raw=datasets.fertility.load_pandas().data
    valid_codes={c.alpha_3 for c in pycountry.countries}
    excluded=sorted(set(raw['Country Code'].dropna().astype(str))-valid_codes)
    rows=[]
    for _,row in raw.iterrows():
        code=str(row['Country Code'])
        if code not in valid_codes:continue
        values={year:float(row[str(year)]) if pd.notna(row[str(year)]) else np.nan for year in range(1960,2014)}
        for year in range(1965,2013):
            curr=values[year];nxt=values[year+1]
            past=np.array([values[year-j] for j in (1,2,3,5)],dtype=float)
            if not (np.isfinite(curr) and np.isfinite(nxt) and np.isfinite(past).all()):continue
            x=[curr,*past,curr-past[0],curr-past[2],(curr+past[0]+past[1])/3,year-1985]
            label=int(nxt-curr<=-.05)
            rows.append({'country_code':code,'country':str(row['Country Name']),
                         'year':year,'key':f'{code}:{year}','y':label,**dict(zip(COLUMNS,x))})
    panel=pd.DataFrame(rows).sort_values(['year','country_code']).reset_index(drop=True)
    for stage,(a,b) in protocol['slices_t_inclusive'].items():
        panel.loc[panel['year'].between(a,b),'stage']=stage
    if panel['stage'].isna().any():
        panel=panel.loc[panel['stage'].notna()].reset_index(drop=True)
    if any(sum(panel.stage==z)==0 for z in STAGES):raise ValueError('empty stage')
    assert not panel.duplicated(['country_code','year']).any()
    return panel,excluded


def base_model(name,seed):
    if name=='logistic_regression':
        return make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=2000,random_state=seed))
    if name=='decision_tree':
        return DecisionTreeClassifier(max_depth=5,min_samples_leaf=15,splitter='random',random_state=seed)
    if name=='random_forest':
        return RandomForestClassifier(n_estimators=40,max_depth=7,min_samples_leaf=5,
                                      max_features=.65,random_state=seed,n_jobs=1)
    if name=='extra_trees':
        return ExtraTreesClassifier(n_estimators=40,max_depth=7,min_samples_leaf=5,
                                    max_features=.65,random_state=seed,n_jobs=1)
    raise KeyError(name)


def train_error_model(z,error):
    if len(np.unique(error))<2:
        # Explicit uninformative constant ranker if historical errors all same.
        # All predictions in that stage have the same empirical error event.
        p=float(np.mean(error))
        return None,p
    clf=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=2000))
    clf.fit(z,error)
    return clf,None

def score_error_model(model,z,constant):
    return np.full(len(z),constant) if model is None else model.predict_proba(z)[:,1]


def run(protocol,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    panel,excluded=make_panel(protocol)
    train=panel[panel.stage=='train'];rest=panel[panel.stage!='train'].copy()
    xtr=train[COLUMNS].to_numpy(); ytr=train.y.to_numpy()
    xr=rest[COLUMNS].to_numpy();yr=rest.y.to_numpy()
    n_aux=protocol['auxiliary_seeds']['stop_exclusive']-protocol['auxiliary_seeds']['start']
    all_case=[];all_cell=[];all_year=[];fcount=0
    for name in MODELS:
        t0=time.monotonic(); p=[]
        for seed in [protocol['reference_seed']]+list(range(protocol['auxiliary_seeds']['start'],protocol['auxiliary_seeds']['stop_exclusive'])):
            estimator=base_model(name,seed)
            estimator.fit(xtr,ytr)
            p.append(estimator.predict_proba(xr)[:,1])
            fcount+=1
        p=np.vstack(p)
        refp=p[0]; refclass=(refp>=.5).astype(int)
        err=(refclass!=yr).astype(int)
        auxp=p[1:]
        d=np.mean((auxp>=.5)!=refclass[None,:],axis=0)
        std=np.std(auxp,axis=0,ddof=0)
        confidence=np.maximum(refp,1-refp)
        # Reference class participates in both error predictors, with no
        # preference for one class and no use of heldout error labels.
        z0=np.column_stack((1-confidence,refclass))
        z1=np.column_stack((1-confidence,refclass,d,std,(1-confidence)*d))
        is_risk=rest.stage=='risk_fit'
        bmodel,bconst=train_error_model(z0[is_risk],err[is_risk])
        amodel,aconst=train_error_model(z1[is_risk],err[is_risk])
        bscore=score_error_model(bmodel,z0,bconst)
        ascore=score_error_model(amodel,z1,aconst)
        is_cal=rest.stage=='review_threshold_calibration'
        brule=choose_threshold(bscore[is_cal],rest.loc[is_cal,'key'].tolist(),protocol['budget'],71250)
        arule=choose_threshold(ascore[is_cal],rest.loc[is_cal,'key'].tolist(),protocol['budget'],71250)
        b=review_masks(bscore,rest.key.tolist(),brule,71250)
        a=review_masks(ascore,rest.key.tolist(),arule,71250)
        gains=policy_gain(err,b,a,protocol['lambda'])
        record=rest[['country_code','year','key','stage','y']].copy()
        record['model']=name;record['reference_class']=refclass
        record['reference_probability']=refp;record['confidence']=confidence
        record['disagreement']=d;record['probability_std']=std
        record['reference_error']=err;record['baseline_score']=bscore;record['augmented_score']=ascore
        record['baseline_review']=b.astype(int);record['augmented_review']=a.astype(int)
        record['gain']=gains;all_case.append(record)
        mon=record[record.stage=='labelled_target_monitoring']
        yrs=mon.groupby('year',sort=True).agg(n=('key','size'),
             gain_mean=('gain','mean'),switch_fraction=('gain',lambda x:float(np.mean(x!=0))),
             baseline_reviews=('baseline_review','sum'),augmented_reviews=('augmented_review','sum'),
             errors=('reference_error','sum')).reset_index()
        # Note switch_fraction from gain!=0 is equivalent to mask switch for lambda=.25
        benefits=mixture_path(yrs.gain_mean)
        harms=mixture_path(yrs.gain_mean,side='harm')
        yrs['model']=name;yrs['e_benefit']=benefits;yrs['e_harm']=harms
        all_year.append(yrs)
        first=first_evidence_time(benefits,.05)
        activate=first is not None
        for stage in ['labelled_target_monitoring','frozen_future_evaluation']:
            q=record[record.stage==stage]
            e=q.reference_error.to_numpy();bb=q.baseline_review.to_numpy();aa=q.augmented_review.to_numpy()
            baseline_cost=method_cost(e,bb,protocol['lambda'])
            augmented_cost=method_cost(e,aa,protocol['lambda'])
            counterfactual_gain=baseline_cost-augmented_cost
            deployed_cost=(augmented_cost if activate else baseline_cost)
            all_cell.append({'model':name,'stage':stage,'n':len(q),
                 'country_count':q.country_code.nunique(),'reference_error_n':int(e.sum()),
                 'baseline_cost':baseline_cost,'augmented_cost':augmented_cost,
                 'augmented_gain':counterfactual_gain,'baseline_reviews':int(bb.sum()),
                 'augmented_reviews':int(aa.sum()),'switch_rate':float(np.mean(bb!=aa)),
                 'positive_e_final':float(benefits[-1]),'negative_e_final':float(harms[-1]),
                 'anytime_positive_alarm':bool(activate),'positive_first_year':int(yrs.year.iloc[first-1]) if first else None,
                 'deployed_cost':deployed_cost,'local_training_seconds':time.monotonic()-t0})
        print(name,'monitor n',len(mon),'e_value',round(float(benefits[-1]),3),'alarm',activate,'future gain',round(float(all_cell[-1]['augmented_gain']),6),'seconds',round(time.monotonic()-t0,1),flush=True)
    cases=pd.concat(all_case,ignore_index=True)
    cells=pd.DataFrame(all_cell)
    years=pd.concat(all_year,ignore_index=True)
    cases.to_csv(out/'R7_CASE_LEVEL.csv',index=False,float_format='%.12g')
    cells.to_csv(out/'R7_POLICY_CELLS.csv',index=False,float_format='%.12g')
    years.to_csv(out/'R7_YEAR_EVIDENCE.csv',index=False,float_format='%.12g')
    obs=panel.groupby('stage').agg(n=('key','size'),countries=('country_code','nunique'),positives=('y','sum')).reset_index()
    obs.to_csv(out/'R7_STAGE_COUNTS.csv',index=False)
    receipt={'protocol_sha256':_sha(Path(__file__).resolve().parent.parent/'PROTOCOL_R7.json'),
             'fit_count':fcount,'model_families':MODELS,'auxiliary_per_model':n_aux,
             'panel_rows':len(panel),'panels_stage':obs.to_dict(orient='records'),
             'excluded_non_iso_country_codes':excluded,
             'result_sha256':{f.name:_sha(f) for f in sorted(out.glob('*.csv'))},
             'data_source':'statsmodels 0.14.6 fertility dataset, World Bank WDI'}
    (out/'R7_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
    print('fits',fcount,'panel',len(panel),'stages',obs.to_string(index=False))
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--protocol',default='../PROTOCOL_R7.json')
    parser.add_argument('--out',default='../results/panel')
    args=parser.parse_args()
    protocol=json.load(open(args.protocol))
    run(protocol,Path(args.out))
