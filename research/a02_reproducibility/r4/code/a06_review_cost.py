"""Exploratory held-out automation-error plus review-workload cost analysis.

This is not clinical/social utility: L_lambda=accepted_errors/n + lambda*reviewed/n,
where lambda is the review effort in units of one automated error. There is no
assumption that a reviewer is perfectly accurate; reviewed outcomes are simply
outside the automated stream. Values at lambda=0 are cost-free review and can
favour higher review volume. No lambda is estimated or optimized from test data.
"""
import argparse
from pathlib import Path
import pandas as pd

LAMBDA_GRID=(0.,0.01,0.025,0.05,0.1,0.2,0.5,1.)
METHODS=('confidence_only','combined_fixed')
DATASETS=('fair','randhie','modechoice','anes')

def compute(source:Path)->tuple[pd.DataFrame,pd.DataFrame]:
    frames=[pd.read_csv(source/d/'A06_SUMMARY.csv') for d in DATASETS]
    d=pd.concat(frames,ignore_index=True)
    d=d[(d.evaluation=='streaming_frozen') & (d.tie_seed==1) & d.policy.isin(METHODS)]
    if len(d)!=64 or d.groupby('cell').size().ne(2).any():raise ValueError('Expected two frozen-streaming policies in every one of 32 cells.')
    rows=[]
    for cell,g in d.groupby('cell'):
        ref=g.set_index('policy')
        b,a=(ref.loc[p] for p in METHODS)
        if int(a.n)!=int(b.n):raise ValueError(f'population mismatch {cell}')
        n=int(a.n)
        error_gap=(int(a.accepted_errors)-int(b.accepted_errors))/n
        review_gap=(int(a.reviewed)-int(b.reviewed))/n
        if error_gap<=0 and review_gap<=0 and (error_gap<0 or review_gap<0): outcome='PARETO_BETTER'
        elif error_gap>=0 and review_gap>=0 and (error_gap>0 or review_gap>0): outcome='PARETO_WORSE'
        elif error_gap==0 and review_gap==0: outcome='SAME'
        else: outcome='TRADEOFF'
        for lam in LAMBDA_GRID:
            delta=error_gap+lam*review_gap
            rows.append({'cell':cell,'dataset':a.dataset,'model':a.model,'lambda_review_per_error':lam,
                         'n':n,'base_accepted_errors':int(b.accepted_errors),'combined_accepted_errors':int(a.accepted_errors),
                         'base_reviewed':int(b.reviewed),'combined_reviewed':int(a.reviewed),
                         'delta_auto_errors_per_100':100*error_gap,'delta_reviews_per_100':100*review_gap,
                         'delta_cost_per_100':100*delta,'pareto_category':outcome,
                         'outcome':'improved' if delta < -1e-12 else ('worsened' if delta > 1e-12 else 'tied')})
    table=pd.DataFrame(rows)
    summary=(table.groupby('lambda_review_per_error',as_index=False)
          .agg(cells=('cell','size'), improved=('outcome',lambda x:(x=='improved').sum()),
               tied=('outcome',lambda x:(x=='tied').sum()),worsened=('outcome',lambda x:(x=='worsened').sum()),
               unweighted_mean_delta_cost_per_100=('delta_cost_per_100','mean'),
               min_delta_cost_per_100=('delta_cost_per_100','min'),
               max_delta_cost_per_100=('delta_cost_per_100','max')))
    return table,summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    t,s=compute(a.results)
    t.to_csv(a.out/'A06_REVIEW_COST_BY_CELL.csv',index=False)
    s.to_csv(a.out/'A06_REVIEW_COST_SUMMARY.csv',index=False)
    print(s.to_string(index=False,float_format=lambda x:f'{x:.5f}'))
    print('Pareto types',t[t.lambda_review_per_error==0].pareto_category.value_counts().to_dict())
if __name__=='__main__':main()
