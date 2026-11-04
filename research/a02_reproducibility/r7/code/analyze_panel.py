"""R7 transparent descriptive summaries; none of the bootstraps are guarantees."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from evidence import mixture_path,first_evidence_time


def analysis(folder, out):
    folder=Path(folder);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    c=pd.read_csv(folder/'R7_CASE_LEVEL.csv');p=pd.read_csv(folder/'R7_POLICY_CELLS.csv')
    rng=np.random.default_rng(71888)
    rows=[];year_rows=[]
    for name,df in c[c.stage.isin(['labelled_target_monitoring','frozen_future_evaluation'])].groupby('model',sort=True):
        monitoring=df[df.stage=='labelled_target_monitoring'].sort_values(['year','country_code'])
        e_naive=mixture_path(monitoring.gain.to_numpy())
        annual=monitoring.groupby('year').gain.mean()
        e_year=mixture_path(annual.to_numpy())
        future=df[df.stage=='frozen_future_evaluation'].sort_values(['year','country_code'])
        years_future=future.groupby('year').gain.mean()
        # Two exploratory uncertainty summaries: one naively assumes rows IID,
        # the other treats years as the resampling units. Both are descriptive.
        rv=future.gain.to_numpy();y=years_future.to_numpy()
        ci_row=np.quantile(np.mean(rng.choice(rv,(4000,len(rv)),replace=True),axis=1),[.025,.975]).tolist()
        ci_year=np.quantile(np.mean(rng.choice(y,(4000,len(y)),replace=True),axis=1),[.025,.975]).tolist()
        q=p[(p.model==name)&(p.stage=='frozen_future_evaluation')].iloc[0]
        rows.append({'model':name,'monitor_case_n':len(monitoring),'monitor_years':len(annual),
                     'monitor_gain':float(monitoring.gain.mean()),
                     'naive_rowwise_max_e':float(e_naive.max()),
                     'naive_rowwise_first_alarm_case':first_evidence_time(e_naive),
                     'group_respecting_max_e':float(e_year.max()),
                     'group_respecting_first_alarm_year':int(annual.index[first_evidence_time(e_year)-1]) if first_evidence_time(e_year) else None,
                     'future_n':len(future),'future_years':len(years_future),
                     'future_gain':float(future.gain.mean()),
                     'future_gain_bootstrap_rows_exploratory':ci_row,
                     'future_gain_bootstrap_years_exploratory':ci_year,
                     'future_baseline_reviews':int(q.baseline_reviews),
                     'future_augmented_reviews':int(q.augmented_reviews),
                     'future_baseline_cost':float(q.baseline_cost),'future_augmented_cost':float(q.augmented_cost),
                     'promoted':bool(q.anytime_positive_alarm)})
        for year,x in future.groupby('year'):
            year_rows.append({'model':name,'year':int(year),'n':len(x),'gain':float(x.gain.mean()),'switch_fraction':float(np.mean(x.baseline_review!=x.augmented_review))})
    a={'protocol_stage':'descriptive post-hoc analysis of frozen panel outputs',
       'model_families':len(rows),'rows':rows,'notice':'Naive rowwise e-values are invalid under unknown within-year dependence; year-level inference conditional on null assumptions only; bootstraps descriptive'}
    (out/'R7_DIAGNOSTICS.json').write_text(json.dumps(a,indent=2)+'\n')
    pd.DataFrame(year_rows).to_csv(out/'R7_FUTURE_BY_YEAR.csv',index=False,float_format='%.12g')
    for r in rows:print(r['model'],'future gain',r['future_gain'],'naive Emax',r['naive_rowwise_max_e'],'year Emax',r['group_respecting_max_e'],'rowCI',r['future_gain_bootstrap_rows_exploratory'],'yearCI',r['future_gain_bootstrap_years_exploratory'])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--results',default='../results/panel');ap.add_argument('--out',default='../results/analysis');args=ap.parse_args();analysis(args.results,args.out)
