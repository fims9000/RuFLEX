"""R6: Pareto and exact cost frontiers from frozen policy-switch evidence.

No new model fits, no post-test policy retuning. The output is a
retrospective sensitivity analysis across the full 0<=review cost<=1 axis.
"""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from pathlib import Path
import numpy as np


def read_rows(p):
    with open(p,encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def save_rows(p,rows):
    with open(p,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def frontier(row):
    n=int(row['n']);review_delta=int(row['augmented_review_n'])-int(row['baseline_review_n'])
    catch_delta=int(row['net_errors_avoided'])
    # Combined cost minus baseline = -catch_delta+lambda*review_delta
    if review_delta<=0 and catch_delta>=0 and (review_delta<0 or catch_delta>0):status='AUGMENTED_PARETO_DOMINATES'
    elif review_delta>=0 and catch_delta<=0 and (review_delta>0 or catch_delta<0):status='BASELINE_PARETO_DOMINATES'
    elif review_delta==0 and catch_delta==0:status='IDENTICAL_COST'
    else:status='COST_DEPENDENT_TRADEOFF'
    breakpoint=catch_delta/review_delta if review_delta else None
    # strict advantage of augmented at a given lambda
    costs=[0.0,0.05,0.10,0.25,0.5,0.75,1.0]
    a={f'augmented_gain_lambda_{v:.2f}':(catch_delta-v*review_delta)/n for v in costs}
    return {'study':row['study'],'dataset':row['dataset'],'model':row['model'],
       'fold':row['fold'],'cell':row['cell'],'mode':row['mode'],'n':n,
       'net_errors_caught':catch_delta,'net_extra_reviews':review_delta,
       'pareto_status':status,'break_even_lambda':breakpoint,
       'switch_fraction':float(row['switch_fraction']),**a}


def compute(src,out):
    rows=[frontier(r) for r in read_rows(src)]
    save_rows(out/'R6_COST_FRONTIERS.csv',rows)
    by=defaultdict(list)
    for x in rows:by[(x['study'],x['mode'])].append(x)
    summary=[]
    for (study,mode),xs in sorted(by.items()):
        vals={c:sum(x['pareto_status']==c for x in xs) for c in
             ('AUGMENTED_PARETO_DOMINATES','BASELINE_PARETO_DOMINATES','IDENTICAL_COST','COST_DEPENDENT_TRADEOFF')}
        summary.append({'study':study,'mode':mode,'cells':len(xs),**vals})
    save_rows(out/'R6_COST_FRONTIER_SUMMARY.csv',summary)
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--switch-csv',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(compute(a.switch_csv,a.out),indent=2))

if __name__=='__main__':main()
