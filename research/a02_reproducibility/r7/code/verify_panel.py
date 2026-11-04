"""Independent R7 case-level policy, accounting and annual e-value replay.

No model fitting: recomputes every frozen review mask from the saved score
columns and the calibration stage, then every gain, cost and annual wealth.
"""
from pathlib import Path
import argparse,hashlib,json
import pandas as pd
import numpy as np
from evidence import choose_threshold,review_masks,policy_gain,method_cost,mixture_path,first_evidence_time

STAGES=('train','risk_fit','review_threshold_calibration','labelled_target_monitoring','frozen_future_evaluation')

def verify(folder,protocol_path):
    root=Path(folder);proto=json.load(open(protocol_path));rcpt=json.load(open(root/'R7_RECEIPT.json'))
    assert hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest()==rcpt['protocol_sha256']
    for n,sha in rcpt['result_sha256'].items():
        assert hashlib.sha256((root/n).read_bytes()).hexdigest()==sha,(n,'checksum failure')
    case=pd.read_csv(root/'R7_CASE_LEVEL.csv',keep_default_na=False)
    cells=pd.read_csv(root/'R7_POLICY_CELLS.csv'); year=pd.read_csv(root/'R7_YEAR_EVIDENCE.csv')
    assert case.key.str.contains(r'^[A-Z]{3}:\d{4}$',regex=True).all()
    assert case.duplicated(['model','key']).sum()==0
    assert set(case.stage)==set(STAGES)-{'train'}
    if len(case.model.unique())!=4:raise AssertionError('missing models')
    checked=0
    for model,subset in case.groupby('model',sort=True):
        # Recompute BOTH thresholds from cal scores, ignoring any saved masks.
        cal=subset[subset.stage=='review_threshold_calibration']
        scb=choose_threshold(cal.baseline_score.to_numpy(),cal.key.tolist(),proto['budget'],71250)
        sca=choose_threshold(cal.augmented_score.to_numpy(),cal.key.tolist(),proto['budget'],71250)
        b=review_masks(subset.baseline_score.to_numpy(),subset.key.tolist(),scb,71250)
        a=review_masks(subset.augmented_score.to_numpy(),subset.key.tolist(),sca,71250)
        assert np.array_equal(b,subset.baseline_review.to_numpy().astype(bool)),(model,'base policy mask mismatch')
        assert np.array_equal(a,subset.augmented_review.to_numpy().astype(bool)),(model,'aug policy mask mismatch')
        e=subset.reference_error.to_numpy()
        assert np.array_equal(e,(subset.y!=subset.reference_class).astype(int).to_numpy())
        g=policy_gain(e,b,a,proto['lambda'])
        assert np.allclose(g,subset.gain.to_numpy(),atol=5e-10),model
        monitor=subset[subset.stage=='labelled_target_monitoring'].sort_values(['year','country_code'])
        years=monitor.groupby('year').gain.mean()
        pos=mixture_path(years.to_numpy())
        neg=mixture_path(years.to_numpy(),side='harm')
        yoy=year[year.model==model].sort_values('year')
        assert np.array_equal(years.index.values,yoy.year.to_numpy())
        assert np.allclose(years.to_numpy(),yoy.gain_mean.to_numpy(),atol=1e-10)
        assert np.allclose(pos,yoy.e_benefit.to_numpy(),atol=1e-10)
        assert np.allclose(neg,yoy.e_harm.to_numpy(),atol=1e-10)
        activated=first_evidence_time(pos,proto['evalue']['alpha']) is not None
        for stage in ['labelled_target_monitoring','frozen_future_evaluation']:
            idx=subset.stage==stage
            q=subset[idx];line=cells[(cells.model==model)&(cells.stage==stage)].iloc[0]
            bj=review_masks(q.baseline_score.to_numpy(),q.key.tolist(),scb,71250)
            aj=review_masks(q.augmented_score.to_numpy(),q.key.tolist(),sca,71250)
            ec=q.reference_error.to_numpy()
            base=method_cost(ec,bj,proto['lambda']);aug=method_cost(ec,aj,proto['lambda'])
            assert abs(base-line.baseline_cost)<5e-10
            assert abs(aug-line.augmented_cost)<5e-10
            assert abs((base-aug)-line.augmented_gain)<5e-10
            assert int(bj.sum())==int(line.baseline_reviews)
            assert int(aj.sum())==int(line.augmented_reviews)
            assert bool(line.anytime_positive_alarm)==activated
            assert abs(line.deployed_cost-(aug if activated else base))<5e-10
        checked+=len(subset)
    assert checked==len(case)
    out={'status':'PASS','models':len(case.model.unique()),'case_model_records':len(case),
         'test_rows':int(sum(case.stage=='frozen_future_evaluation')),
         'fit_count':rcpt['fit_count'],'protocol_sha256':rcpt['protocol_sha256'],
         'all_calibration_thresholds_recomputed':True,
         'all_review_masks_recomputed':True,
         'all_gain_cost_year_evalues_recomputed':True}
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',default='../results/panel');p.add_argument('--protocol',default='../PROTOCOL_R7.json')
    args=p.parse_args()
    print(json.dumps(verify(args.results,args.protocol),indent=2))
