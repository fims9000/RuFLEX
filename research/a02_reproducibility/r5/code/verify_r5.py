"""Independent read-only replay of frozen R5 results from saved case-level rows."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from r5_core import frozen_stream_review,batch_exact_review,policy_metrics,FrozenThreshold
from run_temporal_co2 import make_co2_task,split_by_calendar


def check_close(actual,expected,tol=1e-10):
    if actual is None or expected is None:
        if not (actual is None and (expected is None or pd.isna(expected))):
            raise AssertionError((actual,expected))
        return
    if not np.isclose(float(actual),float(expected),atol=tol,rtol=0):
        raise AssertionError((actual,expected))


def verify(results,protocol):
    p=json.loads(protocol.read_text())
    receipt=json.loads((results/'R5_TEMPORAL_RECEIPT.json').read_text())
    if hashlib.sha256(protocol.read_bytes()).hexdigest()!=receipt['protocol_sha256']:
        raise AssertionError('protocol SHA changed')
    for filename,digest in receipt['files_sha256'].items():
        if hashlib.sha256((results/filename).read_bytes()).hexdigest()!=digest:
            raise AssertionError('frozen CSV modified '+filename)
    frame=pd.read_csv(results/'CASE_LEVEL_TEMPORAL.csv')
    summaries=pd.read_csv(results/'POLICY_OUTCOMES.csv')
    if set(frame.fold)!=set(x['name'] for x in p['temporal_folds']):
        raise AssertionError('unexpected temporal fold')
    original, _, _, dates, _ = make_co2_task()
    if hashlib.sha256(original.to_csv().encode()).hexdigest()!=receipt['dataset_sha256']:
        raise AssertionError('statsmodels source revision changed')
    total=0; unique_cases=0
    for (fold,model),grp in frame.groupby(['fold','model'],sort=True):
        if grp.date.duplicated().any() or not pd.to_datetime(grp.date).is_monotonic_increasing:
            raise AssertionError('duplicated/unsorted temporal cases')
        fld=next(x for x in p['temporal_folds'] if x['name']==fold)
        ix=split_by_calendar(dates,fld)[2]
        expected_dates=[str(pd.Timestamp(d).date()) for d in dates[ix]]
        if grp.date.tolist()!=expected_dates:
            raise AssertionError('heldout row identities do not match temporal split')
        y=grp.truth.to_numpy(dtype=int)
        pred=grp.reference_prediction.to_numpy(dtype=int)
        if not np.array_equal(grp.reference_is_wrong.to_numpy(dtype=int), y!=pred):
            raise AssertionError('error label mismatch')
        for policy in p['candidate_risk_rankers']:
            for mode in ('stream','batch'):
                found=summaries[(summaries.fold==fold)&(summaries.model==model)&
                                (summaries.policy==policy)&(summaries['mode']==mode)]
                if len(found)!=1:raise AssertionError('missing or duplicate policy summary')
                sm=found.iloc[0]
                z=grp['risk_'+policy].to_numpy(dtype=float)
                if mode=='stream':
                    threshold=FrozenThreshold(float(sm.calibration_cutoff),float(sm.calibration_tie_p),
                                              requested_count=0,n_calibration=0)
                    masks=frozen_stream_review(z,grp.date.tolist(),threshold,55043)
                else:
                    masks=batch_exact_review(z,grp.date.tolist(),p['review_budget'],55043)
                saved=grp['review_'+policy+'_'+mode].to_numpy(dtype=bool)
                if not np.array_equal(masks,saved):
                    raise AssertionError(f'review-mask mismatch: {fold}/{model}/{policy}/{mode}')
                if mode=='batch' and masks.sum()!=int(np.ceil(len(y)*p['review_budget']-1e-12)):
                    raise AssertionError('batch not exactly budget matched')
                metrics=policy_metrics(y,pred,masks,p['review_cost_lambda'])
                for k,v in metrics.items():check_close(v,sm[k])
                total+=1
        unique_cases+=len(grp)
    if total != 64 or unique_cases != 2820:
        raise AssertionError(('unexpected counted cells/rows',total,unique_cases))
    return {'status':'PASS','verified_policy_summaries':total,'verified_case_model_predictions':unique_cases,
            'protocol_sha256':receipt['protocol_sha256'],'source_results_sha256':receipt['files_sha256']}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    result=verify(args.results,args.protocol)
    (args.results/'R5_INDEPENDENT_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
