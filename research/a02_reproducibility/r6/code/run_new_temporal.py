"""R6 locked real temporal out-of-period study: sunspots and US macro.

Five chronological partitions: fit base model -> fit conditional error model ->
set unlabeled review thresholds -> assess new-policy value with labeled
certification cases -> evaluate untouched final window.

The iid certificate is interpreted as a diagnostic only on time-dependent
observations; it is *not* an unconditional temporal reliability guarantee.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys
from pathlib import Path
import numpy as np
import statsmodels.api as sm
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression,SGDClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from switch_theory import paired_switch_summary,switch_set_certificate


def write_rows(path,rows):
    if not rows:raise ValueError('empty rows')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def series_bundles():
    """Only current/past observations are predictors. Target is t+1."""
    sun=sm.datasets.sunspots.load_pandas().data
    arr=np.asarray(sun['SUNACTIVITY'],float)
    years=np.asarray(sun['YEAR'],int)
    x=[];y=[];ids=[]
    for t in range(6,len(arr)-1):
        lag=arr[t-6:t+1]
        feat=[arr[t],arr[t-1],arr[t-2],arr[t-3],arr[t-6],
              arr[t]-arr[t-1],arr[t]-arr[t-3],
              float(lag[-3:].mean()),float(lag.mean()),
              math.sin(2*math.pi*years[t]/11),math.cos(2*math.pi*years[t]/11)]
        x.append(feat);y.append(int(arr[t+1]>arr[t]));ids.append(str(years[t]))
    macro=sm.datasets.macrodata.load_pandas().data
    U=np.asarray(macro['unemp'],float);I=np.asarray(macro['infl'],float)
    C=np.asarray(macro['cpi'],float);GDP=np.asarray(macro['realgdp'],float)
    T=np.asarray(macro['tbilrate'],float);R=np.asarray(macro['realint'],float)
    Q=np.asarray(macro['quarter'],int);Yr=np.asarray(macro['year'],int)
    xx=[];yy=[];dates=[]
    for t in range(3,len(U)-1):
        feat=[U[t],U[t-1],U[t-2],I[t],I[t-1],C[t],T[t],R[t],
              100*math.log(GDP[t]/GDP[t-1]),100*math.log(GDP[t-1]/GDP[t-2]),
              math.sin(2*math.pi*Q[t]/4),math.cos(2*math.pi*Q[t]/4)]
        xx.append(feat);yy.append(int(U[t+1]>U[t]));dates.append(f'{Yr[t]}Q{Q[t]}')
    return [("sunspots_next_year_rise",np.asarray(x,float),np.asarray(y,int),ids),
            ("us_macro_next_quarter_unemployment_rise",np.asarray(xx,float),np.asarray(yy,int),dates)]


def partitions(n):
    u=n-4
    if u<50:raise ValueError('not enough temporal rows')
    lens=[int(.45*u),int(.20*u),int(.10*u),int(.10*u)]
    lens.append(u-sum(lens))
    out=[];st=0
    for i,le in enumerate(lens):
        out.append(np.arange(st,st+le,dtype=int));st+=le+int(i<4)
    assert st==n and sum(map(len,out))+4==n
    for i in range(4):assert out[i+1][0]-out[i][-1]>=2
    return out


def make_model(family,seed):
    if family=='logistic_regression':return LogisticRegression(max_iter=1000,solver='lbfgs',random_state=seed)
    if family=='decision_tree':return DecisionTreeClassifier(min_samples_leaf=3,max_depth=8,random_state=seed)
    if family=='random_forest':return RandomForestClassifier(n_estimators=24,max_features='sqrt',min_samples_leaf=3,n_jobs=1,random_state=seed)
    if family=='sgd_log_loss':return SGDClassifier(loss='log_loss',alpha=.0001,max_iter=1500,tol=.0001,random_state=seed)
    raise ValueError(family)


def feature_matrix(ref_p,pred,audit_p,audit_labels,augmented):
    conf=np.maximum(ref_p,1-ref_p)
    disag=np.mean(audit_labels!=pred[:,None],axis=1)
    disper=np.std(audit_p,axis=1)
    col=[1-conf,pred.astype(float)]
    if augmented:col.extend([disag,disper,(1-conf)*disag])
    return np.column_stack(col),disag,disper,conf


def train_risk_model(x,y):
    if len(np.unique(y))<2:return DummyClassifier(strategy='constant',constant=int(y[0])).fit(x,y)
    return make_pipeline(StandardScaler(),LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,random_state=61043)).fit(x,y)


def predict_err(m,x):
    p=m.predict_proba(x);classes=m.classes_ if hasattr(m,'classes_') else m[-1].classes_
    return p[:,list(classes).index(1)] if 1 in classes else np.zeros(len(x))


def tie_hash(s:str)->float:
    h=hashlib.sha256(f'R6|61042|{s}'.encode('utf-8')).digest()
    return int.from_bytes(h[:8],'big')/2**64


def fit_threshold(scores,budget):
    v=np.asarray(scores,float);k=math.ceil(budget*len(v)-1e-12)
    t=float(np.sort(v)[-k]);gt=int(np.count_nonzero(v>t));eq=int(np.count_nonzero(v==t))
    return t,(k-gt)/eq


def apply_threshold(scores,identities,threshold):
    t,p=threshold
    z=np.asarray(scores,float)
    return (z>t)|((z==t)&(np.array([tie_hash(x) for x in identities])<p))


def metrics(e,review,lam):
    e=np.asarray(e,bool);review=np.asarray(review,bool)
    return {'reviewed':int(review.sum()),'review_fraction':float(np.mean(review)),
      'automated_errors':int(np.sum(e&~review)),
      'total_errors':int(e.sum()),
      'joint_cost':float(np.mean((e&~review).astype(float)+lam*review.astype(float)))}


def run(protocol_path,out):
    raw=Path(protocol_path).read_bytes();p=json.loads(raw)
    assert p['id']=='R6_SWITCH_VALUE_AND_TRANSPORTABILITY_20261104'
    assert p['reference_fit_seed']==61000 and p['audit_seeds_stop_exclusive']==61017
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    all_rows=[];case_rows=[];cert_rows=[];cert_case_rows=[];thresh_case_rows=[];cells=[];train_fits=0
    for data_id,X,y,ids in series_bundles():
        slices=partitions(len(y))
        train,riskfit,thresh,cert,test=slices
        assert len(set(y[train]))==2,(data_id,np.unique(y[train]))
        scal=StandardScaler().fit(X[train]);tx=scal.transform(X)
        for family in p['models']:
            ref=make_model(family,p['reference_fit_seed']).fit(tx[train],y[train]);train_fits+=1
            aux=[make_model(family,s).fit(tx[train],y[train]) for s in range(p['audit_seeds_start'],p['audit_seeds_stop_exclusive'])]
            train_fits+=len(aux)
            p_ref=ref.predict_proba(tx)[:,1];ref_class=np.asarray(ref.predict(tx),int)
            ap=np.column_stack([m.predict_proba(tx)[:,1] for m in aux])
            al=np.column_stack([m.predict(tx) for m in aux])
            risk_x0,d,s,c=feature_matrix(p_ref,ref_class,ap,al,False)
            risk_x1,d,s,c=feature_matrix(p_ref,ref_class,ap,al,True)
            riskfit_errors=(ref_class[riskfit]!=y[riskfit]).astype(int)
            base_model=train_risk_model(risk_x0[riskfit],riskfit_errors);aug_model=train_risk_model(risk_x1[riskfit],riskfit_errors)
            rb=predict_err(base_model,risk_x0);ra=predict_err(aug_model,risk_x1)
            budget=float(p['threshold_calibration_review_fraction']);lam=float(p['review_cost_lambda'])
            tb=fit_threshold(rb[thresh],budget);ta=fit_threshold(ra[thresh],budget)
            cert_b=apply_threshold(rb[cert],[ids[i] for i in cert],tb)
            cert_a=apply_threshold(ra[cert],[ids[i] for i in cert],ta)
            cert_errors=(ref_class[cert]!=y[cert]).astype(int)
            cert_test=switch_set_certificate(cert_errors,cert_b,cert_a,lam=lam,alpha=.05)
            for j,i in enumerate(cert):
                cert_case_rows.append({'dataset':data_id,'model':family,'time_id':ids[i],
                    'reference_error':int(cert_errors[j]),'base_review':int(cert_b[j]),
                    'aug_review':int(cert_a[j]),
                    'base_error_risk_score':float(rb[i]),'aug_error_risk_score':float(ra[i])})
            for i in thresh:
                thresh_case_rows.append({'dataset':data_id,'model':family,'time_id':ids[i],
                    'base_error_risk_score':float(rb[i]),'aug_error_risk_score':float(ra[i])})
            activate=bool(cert_test['certified_positive'])
            # Crucial: no heldout label has been inspected at this point.
            test_b=apply_threshold(rb[test],[ids[i] for i in test],tb)
            test_a=apply_threshold(ra[test],[ids[i] for i in test],ta)
            test_g=test_a if activate else test_b
            test_errors=(ref_class[test]!=y[test]).astype(int)
            mb=metrics(test_errors,test_b,lam);ma=metrics(test_errors,test_a,lam);mg=metrics(test_errors,test_g,lam)
            observed=paired_switch_summary(test_errors,test_b,test_a,lam)
            info={'dataset':data_id,'model':family,'train_n':len(train),'riskfit_n':len(riskfit),
               'thresholdcal_n':len(thresh),'certification_n':len(cert),'test_n':len(test),
               'training_fits':1+len(aux),'reference_error_rate':float(test_errors.mean()),
               'base_review_n':mb['reviewed'],'aug_review_n':ma['reviewed'],'guard_review_n':mg['reviewed'],
               'base_cost':mb['joint_cost'],'aug_cost':ma['joint_cost'],'guard_cost':mg['joint_cost'],
               'aug_gain':mb['joint_cost']-ma['joint_cost'],
               'guard_gain':mb['joint_cost']-mg['joint_cost'],
               'base_auto_errors':mb['automated_errors'],'aug_auto_errors':ma['automated_errors'],
               'switch_frac':observed.switch_fraction,
               'cert_lower_gain':cert_test['lower_gain_confidence'],
               'cert_gain':cert_test['empirical_gain'],'cert_activated':int(activate),
               'test_epsilon_to_erase_gain':observed.fragility_epsilon if observed.gain>0 else None,
               'base_error_brier':float(np.mean((rb[test]-test_errors)**2)),
               'aug_error_brier':float(np.mean((ra[test]-test_errors)**2)),
            }
            all_rows.append(info);cert_rows.append({'dataset':data_id,'model':family,**{k:v for k,v in cert_test.items() if k!='intervals'}})
            for i in test:
                j=np.flatnonzero(test==i)[0]
                case_rows.append({'dataset':data_id,'model':family,'time_id':ids[i],
                    'true_label':int(y[i]),'reference_class':int(ref_class[i]),'reference_error':int(test_errors[j]),
                    'reference_confidence':float(c[i]),'audit_disagreement':float(d[i]),
                    'audit_probability_std':float(s[i]),'base_error_risk_score':float(rb[i]),
                    'aug_error_risk_score':float(ra[i]),'base_review':int(test_b[j]),
                    'aug_review':int(test_a[j]),'guard_review':int(test_g[j])})
            cells.append({'cell':data_id+'/'+family,'dataset_data_sha256':hashlib.sha256(X.tobytes()+y.tobytes()).hexdigest(),
              'first_train':ids[train[0]],'last_train':ids[train[-1]],
              'riskfit_range':[ids[riskfit[0]],ids[riskfit[-1]]],
              'threshold_range':[ids[thresh[0]],ids[thresh[-1]]],
              'certification_range':[ids[cert[0]],ids[cert[-1]]],
              'test_range':[ids[test[0]],ids[test[-1]]],
              'base_threshold':list(tb),'aug_threshold':list(ta)})
            print(data_id,family,'aug_gain',round(info['aug_gain'],5),'cert',activate,flush=True)
    write_rows(out/'R6_TEMPORAL_RESULTS.csv',all_rows)
    write_rows(out/'R6_TEMPORAL_CASE_LEVEL.csv',case_rows)
    write_rows(out/'R6_CERTIFICATION.csv',cert_rows)
    write_rows(out/'R6_CERTIFICATION_CASE_LEVEL.csv',cert_case_rows)
    write_rows(out/'R6_THRESHOLD_CALIBRATION_SCORES.csv',thresh_case_rows)
    manifest={'protocol_sha256':hashlib.sha256(raw).hexdigest(),
      'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'statsmodels_version':sm.__version__,'fit_count':train_fits,
      'new_independent_real_temporal_sources':2,'model_cells':len(all_rows),
      'note':'Two separate source data sets, four correlated model families each; historical observations, not current institutional deployments.',
      'certification_assumption':'IID calibration-to-deployment; NOT established for these time-series, so lower limits are not deployment guarantees.',
      'cells':cells}
    manifest['outputs_sha256']={z:hashlib.sha256((out/z).read_bytes()).hexdigest() for z in ['R6_TEMPORAL_RESULTS.csv','R6_TEMPORAL_CASE_LEVEL.csv','R6_CERTIFICATION.csv','R6_CERTIFICATION_CASE_LEVEL.csv','R6_THRESHOLD_CALIBRATION_SCORES.csv']}
    (out/'R6_TEMPORAL_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    print(json.dumps({'fit_count':run(args.protocol,args.out)['fit_count']}))

if __name__=='__main__':main()
