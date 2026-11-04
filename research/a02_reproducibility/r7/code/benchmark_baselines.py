"""R7 POST-HOC controls. All comparisons reuse frozen case-level scores.

Added after observing R7 outcome. This cannot be called confirmatory evidence.
No target labels enter threshold selection.
"""
from pathlib import Path
import json,argparse
import numpy as np
import pandas as pd
from evidence import choose_threshold,review_masks,method_cost


def run(infile,out,protocol):
    p=json.load(open(protocol));df=pd.read_csv(infile)
    results=[]
    for fam,z in df.groupby('model',sort=True):
        z=z.copy()
        scores={
            'raw_confidence':1-z.confidence.to_numpy(),
            'disagreement_only':z.disagreement.to_numpy(),
            'fixed_confidence_plus_disagreement':(1-z.confidence+.5*z.disagreement).to_numpy(),
            'supervised_confidence':z.baseline_score.to_numpy(),
            'supervised_conditional':z.augmented_score.to_numpy()}
        cal=z.stage=='review_threshold_calibration'
        for score_name,score in scores.items():
            rule=choose_threshold(score[cal],z.loc[cal,'key'].tolist(),p['budget'],71250)
            mask=review_masks(score,z.key.tolist(),rule,71250)
            for stage in ('labelled_target_monitoring','frozen_future_evaluation'):
                idx=z.stage==stage
                e=z.reference_error.to_numpy()[idx]; a=mask[idx]
                results.append({'model':fam,'policy':score_name,'stage':stage,'n':len(e),
                    'review_n':int(a.sum()),'review_fraction':float(a.mean()),
                    'automated_errors':int(np.sum(e[~a])),
                    'joint_cost':method_cost(e,a,p['lambda'])})
    t=pd.DataFrame(results)
    t.to_csv(out,index=False,float_format='%.12g')
    return t
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',default='../results/panel/R7_CASE_LEVEL.csv')
    ap.add_argument('--protocol',default='../PROTOCOL_R7.json')
    ap.add_argument('--out',default='../results/analysis/R7_POSTHOC_BASELINES.csv')
    a=ap.parse_args();x=run(a.cases,a.out,a.protocol)
    print(x.query('stage=="frozen_future_evaluation"').pivot(index='model',columns='policy',values='joint_cost').round(4).to_string())
