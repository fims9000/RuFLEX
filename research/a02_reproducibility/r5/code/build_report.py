"""Read-only R5 plots and summary prose built from frozen independently checked evidence."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent.parent
RESULT=ROOT/'results/temporal_co2'


def main():
    a=pd.read_csv(RESULT/'POLICY_OUTCOMES.csv')
    b=pd.read_csv(ROOT/'results/R5_A06_EXPLORATORY_REANALYSIS.csv')
    rows=[]
    for fold in ('early_secondary','late_primary'):
        for model in ('logistic_regression','decision_tree','random_forest','sgd_log_loss'):
            x=a[(a.fold==fold)&(a.model==model)&(a['mode']=='stream')]
            met=x.set_index('policy')
            cond=met.loc['calibrated_conditional']; base=met.loc['calibrated_confidence']; raw=met.loc['confidence_only_raw']
            exact=a[(a.fold==fold)&(a.model==model)&(a['mode']=='batch')].set_index('policy')
            report=json.loads((RESULT/f'cell_{fold}__{model}.json').read_text())
            rows.append({
                'fold':fold,'model':model,'holdout_n':int(cond.n),'reference_errors':int(cond.total_reference_errors),
                'stream_cost_baseline':float(base.joint_review_cost),'stream_cost_conditional':float(cond.joint_review_cost),
                'stream_cost_delta':float(cond.joint_review_cost-base.joint_review_cost),
                'stream_cost_vs_raw':float(cond.joint_review_cost-raw.joint_review_cost),
                'stream_review_baseline':int(base.reviewed),'stream_review_conditional':int(cond.reviewed),
                'batch_accepted_errors_baseline':int(exact.loc['calibrated_confidence'].accepted_errors),
                'batch_accepted_errors_conditional':int(exact.loc['calibrated_conditional'].accepted_errors),
                'batch_errors_avoided':int(exact.loc['calibrated_confidence'].accepted_errors-exact.loc['calibrated_conditional'].accepted_errors),
                'model_risk_crossings':int(report['crossing_n']),
                'brier_delta':float(report['brier_delta']),
                'bootstrap_ci_low':float(report['stream_cost_moving_block_ci_low']),
                'bootstrap_ci_high':float(report['stream_cost_moving_block_ci_high']),
                'high_confidence_stable_wrong':int(report['high_confidence_stable_wrong_n']),
            })
    d=pd.DataFrame(rows)
    d.to_csv(ROOT/'results/R5_PRIMARY_CONTRASTS.csv',index=False)
    plt.figure(figsize=(10,5))
    vals=100*d.stream_cost_delta.to_numpy()
    lbl=[('Early' if f.startswith('early') else 'Late')+' / '+m.replace('_',' ') for f,m in zip(d.fold,d.model)]
    yy=np.arange(len(vals))
    plt.barh(yy,vals)
    plt.yticks(yy,lbl)
    plt.axvline(0,linewidth=1,color='black')
    plt.xlabel('Additional joint cost (conditional minus confidence), pp')
    plt.title('Exploratory R5 temporal transfer: lower is better')
    plt.grid(axis='x',alpha=.2)
    plt.gca().invert_yaxis()
    plt.tight_layout()
    path=ROOT/'figures/R5_TEMPORAL_COST_DELTA.png'
    plt.savefig(path,dpi=165,bbox_inches='tight')
    plt.close()
    summary={
        'protocol_sha256':json.loads((ROOT/'PROTOCOL_FREEZE_RECEIPT.json').read_text())['protocol_sha256'],
        'new_training_fits':248,'new_temporal_cells':8,
        'new_heldout_case_model_predictions':int(d.holdout_n.sum()),
        'early_stream_improved_tied_worse': [int((d[d.fold=='early_secondary'].stream_cost_delta<-1e-12).sum()),
             int((d[d.fold=='early_secondary'].stream_cost_delta.abs()<=1e-12).sum()),
             int((d[d.fold=='early_secondary'].stream_cost_delta>1e-12).sum())],
        'late_stream_improved_tied_worse': [int((d[d.fold=='late_primary'].stream_cost_delta<-1e-12).sum()),
             int((d[d.fold=='late_primary'].stream_cost_delta.abs()<=1e-12).sum()),
             int((d[d.fold=='late_primary'].stream_cost_delta>1e-12).sum())],
        'late_batch_errors_avoided_per_model':[{'model':r.model,'avoided':int(r.batch_errors_avoided)} for r in d.itertuples() if r.fold=='late_primary'],
        'all_temporal_heldouts_temporally_correlated':True,
    }
    for mode in ('stream','batch'):
        x=b[(b['mode']==mode) & b.policy.isin(['calibrated_conditional','calibrated_confidence'])]
        p=x.pivot(index='cell',columns='policy',values='joint_review_cost')
        delta=p['calibrated_conditional']-p['calibrated_confidence']
        summary['historical_a06_'+mode+'_improved_tied_worse']=[int((delta<-1e-12).sum()),int((delta.abs()<=1e-12).sum()),int((delta>1e-12).sum())]
        summary['historical_a06_'+mode+'_mean_cost_delta']=float(delta.mean())
    (ROOT/'results/R5_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
