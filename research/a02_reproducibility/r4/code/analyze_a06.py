"""Read-only quantitative analysis of A06 frozen scores and held-out labels."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from a06_streaming import POLICIES, batch_reject, freeze_threshold, stream_reject, metrics


def paired_bootstrap_delta(err, selected, baseline, *, groups=None, seed=0, reps=2500):
    """Case or group bootstrap conditional on frozen policies; no re-selection."""
    err=np.asarray(err,dtype=float);a=np.asarray(~selected,dtype=float);b=np.asarray(~baseline,dtype=float)
    if groups is None:
        unique=np.arange(len(err)); inverse=np.arange(len(err))
    else:
        unique,inverse=np.unique(groups,return_inverse=True)
    m=len(unique)
    sa=np.bincount(inverse,weights=err*a,minlength=m)
    na=np.bincount(inverse,weights=a,minlength=m)
    sb=np.bincount(inverse,weights=err*b,minlength=m)
    nb=np.bincount(inverse,weights=b,minlength=m)
    rng=np.random.default_rng(seed);collected=[];invalid=0
    prob=np.full(m,1/m)
    for start in range(0,reps,125):
        nrep=min(125,reps-start)
        # Multinomial bootstrap weights over primary sampling units.
        w=rng.multinomial(m,prob,size=nrep)
        an=w@na;bn=w@nb
        valid=(an>0)&(bn>0)
        invalid+=int(np.sum(~valid))
        if valid.any():
            res=(w[valid]@sa)/an[valid]-(w[valid]@sb)/bn[valid]
            collected.extend(res.tolist())
    if len(collected)<.9*reps:return None,invalid
    return [float(z) for z in np.quantile(collected,[.025,.975])],invalid


def run(results, out):
    roots=[results/z for z in ['fair','randhie','modechoice','anes']]
    dfs=[pd.read_csv(r/'A06_CASE_LEVEL.csv',float_precision='round_trip') for r in roots]
    cells=pd.concat(dfs,ignore_index=True)
    rows=pd.concat([pd.read_csv(r/'A06_SUMMARY.csv',float_precision='round_trip') for r in roots],ignore_index=True)
    seeds=sorted(rows.loc[rows.evaluation=='streaming_frozen','tie_seed'].unique())
    nominal=.9; tie_seed=1
    point=rows[((rows.evaluation=='streaming_frozen')&(rows.tie_seed==tie_seed))|
               (rows.evaluation=='batch_exact_secondary')].copy()
    baseline=point[point.policy=='confidence_only'][['cell','evaluation','coverage','accepted_risk','reviewed','reviewed_errors']].copy()
    baseline=baseline.rename(columns={c:c+'_confidence' for c in ['coverage','accepted_risk','reviewed','reviewed_errors']})
    joined=point.merge(baseline,on=['cell','evaluation'],validate='many_to_one')
    joined['risk_delta_vs_confidence']=joined.accepted_risk-joined.accepted_risk_confidence
    joined['coverage_delta_vs_confidence']=joined.coverage-joined.coverage_confidence
    joined['extra_errors_reviewed']=joined.reviewed_errors-joined.reviewed_errors_confidence
    joined['coverage_abs_deviation']=abs(joined.coverage-nominal)
    # Reconstruct paired, fixed-mask comparisons, including clustered bootstrap for modechoice.
    ci=[]
    for key,g in cells[cells.partition=='heldout'].groupby('cell',sort=True):
        g=g.sort_values('case_id')
        y=g.truth.to_numpy(dtype=int);yp=g.prediction.to_numpy(dtype=int);ids=g.case_id.to_numpy(dtype=int)
        base=batch_reject(g.score_confidence_only.to_numpy(),ids,nominal,tie_seed)
        combo=batch_reject(g.score_combined_fixed.to_numpy(),ids,nominal,tie_seed)
        group=g.group_id.to_numpy(dtype=int) if key.startswith('modechoice_') else None
        digest=hashlib.sha256(key.encode('utf-8')).hexdigest()
        fixed_seed=int(digest[:8],16)
        interval,invalid=paired_bootstrap_delta(y!=yp,combo,base,groups=group,seed=fixed_seed)
        a=metrics(y,yp,combo);b=metrics(y,yp,base)
        ci.append({'cell':key,'dataset':g.dataset.iloc[0],'model':g.model.iloc[0],
          'n':len(y),'n_error':int((y!=yp).sum()),
          'delta_risk':a['accepted_risk']-b['accepted_risk'],
          'ci_lower':interval[0] if interval else None,'ci_upper':interval[1] if interval else None,
          'ci_excludes_zero':bool(interval is not None and (interval[1]<0 or interval[0]>0)),
          'bootstrap_unit':'individual' if group is not None else 'row',
          'invalid_replicates':invalid,'replicates':2500})
    ci=pd.DataFrame(ci)
    comparison=[]
    for (evaluation,policy),g in joined.groupby(['evaluation','policy'],sort=True):
        d=g.risk_delta_vs_confidence.to_numpy()
        comparison.append({'evaluation':evaluation,'policy':policy,'cell_count':len(g),
            'improved':int((d < -1e-12).sum()),'tied':int((abs(d)<=1e-12).sum()),
            'worsened':int((d > 1e-12).sum()),
            'unweighted_mean_delta':float(np.mean(d)),
            'mean_abs_coverage_gap_vs_conf':float(np.mean(abs(g.coverage_delta_vs_confidence))),
            'max_abs_coverage_gap_vs_conf':float(np.max(abs(g.coverage_delta_vs_confidence)))})
    comparison=pd.DataFrame(comparison)
    tie=rows[rows.evaluation=='streaming_frozen'].groupby(['cell','dataset','model','policy'],as_index=False).agg(
        risk_min=('accepted_risk','min'),risk_max=('accepted_risk','max'),
        coverage_min=('coverage','min'),coverage_max=('coverage','max'))
    tie['risk_range']=tie.risk_max-tie.risk_min
    tie['coverage_range']=tie.coverage_max-tie.coverage_min
    # Dataset-level aggregates to avoid presenting 32 correlated cells as 32 independent datasets.
    domain=joined.groupby(['evaluation','dataset','policy'],as_index=False).agg(
       mean_delta=('risk_delta_vs_confidence','mean'),
       min_delta=('risk_delta_vs_confidence','min'),max_delta=('risk_delta_vs_confidence','max'),
       mean_coverage=('coverage','mean'),mean_coverage_gap=('coverage_delta_vs_confidence','mean'))
    out.mkdir(exist_ok=True,parents=True)
    table_items={'A06_POLICY_COMPARISON.csv':comparison,'A06_CELL_CONTRASTS.csv':joined,
                 'A06_BOOTSTRAP_BY_CELL.csv':ci,'A06_TIE_SENSITIVITY.csv':tie,
                 'A06_DOMAIN_COMPARISON.csv':domain}
    for name,df in table_items.items():df.to_csv(out/name,index=False,float_format='%.17g')
    pri=comparison[(comparison.policy=='combined_fixed')].sort_values('evaluation')
    summary={'datasets':int(cells.dataset.nunique()),'cells':int(cells.cell.nunique()),
             'test_case_model_rows':int(sum((g.partition=='heldout').sum() for _,g in cells.groupby('cell'))),
             'validation_and_test_case_rows':int(len(cells)),
             'comparisons':pri.to_dict(orient='records'),
             'bootstrap_intervals_excluding_zero_uncorrected':int(ci.ci_excludes_zero.sum()),
             'bootstrap_intervals_total':len(ci),
             'warning':'Bootstrap CIs are conditional fixed-mask descriptive intervals; non-independent resplits and dataset reuse prohibit 32 independent discovery claims. Streaming tests have unequal realized coverage.'}
    (out/'A06_ANALYSIS_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a.results,a.out),indent=2))

if __name__=='__main__':main()
