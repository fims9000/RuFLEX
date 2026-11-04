"""Exploratory R4 A06 *reanalysis* for the R5 conditional-value hypothesis.

Historical A06 held-out labels were already inspected before R5 conception.
These contrasts can debug and probe a hypothesis but are NOT independent
confirmation; they are never used to change the frozen CO2 R5 protocol.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from r5_core import (risk_features, train_error_model, predict_error_risk,
    frozen_threshold, frozen_stream_review, batch_exact_review, policy_metrics)


def run(r4, out, *, budget=.20, lam=.25, seed=55043):
    all_rows=[]
    for folder in sorted(r4.iterdir()):
        file=folder/'A06_CASE_LEVEL.csv'
        if not file.exists(): continue
        frame=pd.read_csv(file)
        expected={'cell','dataset','split_seed','model','partition','case_id','truth','prediction','confidence','agreement','std'}
        if not expected.issubset(frame.columns): raise ValueError('R4 source missing fields: '+str(file))
        for cell, block in frame.groupby('cell',sort=True):
            val=block[block.partition=='validation'].copy()
            test=block[block.partition=='heldout'].copy()
            if len(val)<20 or len(test)<20 or set(val.case_id)&set(test.case_id):
                raise RuntimeError('missing valid split or leakage '+cell)
            disval=1-val.agreement.to_numpy(dtype=float)
            distest=1-test.agreement.to_numpy(dtype=float)
            def features(rows,d,aug):
                return risk_features(rows.confidence.to_numpy(dtype=float),rows.prediction.to_numpy(dtype=int),
                                     d,rows['std'].to_numpy(dtype=float),augmented=aug)
            err=(val.truth.to_numpy(dtype=int)!=val.prediction.to_numpy(dtype=int)).astype(int)
            baseline=train_error_model(features(val,disval,False),err)
            aug=train_error_model(features(val,disval,True),err)
            val_scores={
                'calibrated_confidence':predict_error_risk(baseline,features(val,disval,False)),
                'calibrated_conditional':predict_error_risk(aug,features(val,disval,True)),
                'confidence_raw':1-val.confidence.to_numpy(dtype=float),
                'combined_fixed':1-val.confidence.to_numpy(dtype=float)+.5*disval,
            }
            test_scores={
                'calibrated_confidence':predict_error_risk(baseline,features(test,distest,False)),
                'calibrated_conditional':predict_error_risk(aug,features(test,distest,True)),
                'confidence_raw':1-test.confidence.to_numpy(dtype=float),
                'combined_fixed':1-test.confidence.to_numpy(dtype=float)+.5*distest,
            }
            ids=[str(cell)+':'+str(int(i)) for i in test.case_id]
            meta={'cell':cell,'dataset':str(val.dataset.iloc[0]),'model':str(val.model.iloc[0]),'split_seed':int(val.split_seed.iloc[0]),
                  'validation_n':len(val),'test_n':len(test),'validation_error_count':int(err.sum())}
            for policy in val_scores:
                threshold=frozen_threshold(val_scores[policy],budget)
                for mode,mask in (
                    ('stream',frozen_stream_review(test_scores[policy],ids,threshold,seed)),
                    ('batch',batch_exact_review(test_scores[policy],ids,budget,seed)),
                ):
                    m=policy_metrics(test.truth.to_numpy(dtype=int),test.prediction.to_numpy(dtype=int),mask,lam)
                    all_rows.append({**meta,'policy':policy,'mode':mode,
                      'brier_error_risk':float(brier_score_loss(test.truth.to_numpy(dtype=int)!=test.prediction.to_numpy(dtype=int),test_scores[policy])) if policy.startswith('calibrated') else None,
                      'boundary_crossings':int(np.sum((test_scores['calibrated_confidence']-lam)*
                                               (test_scores['calibrated_conditional']-lam)<0)),
                      **m})
    out.mkdir(parents=True,exist_ok=True)
    path=out/'R5_A06_EXPLORATORY_REANALYSIS.csv'
    with path.open('w',newline='',encoding='utf8') as fh:
        w=csv.DictWriter(fh,fieldnames=list(all_rows[0]),lineterminator='\n')
        w.writeheader();w.writerows(all_rows)
    return path

if __name__=='__main__':
    pa=argparse.ArgumentParser()
    pa.add_argument('--r4-results',type=Path,required=True)
    pa.add_argument('--out',type=Path,required=True)
    args=pa.parse_args()
    print(run(args.r4_results,args.out))
