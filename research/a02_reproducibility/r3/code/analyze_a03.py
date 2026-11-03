"""A03 read-only study aggregation, Figure data and failure-case selection."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).parents[1]
paths=[ROOT/'results'/'split101',ROOT/'results'/'split202']
out=ROOT/'results'/'analysis';out.mkdir(parents=True,exist_ok=True)
policy=pd.concat([pd.read_csv(x/'A03_POLICY_OUTCOMES.csv') for x in paths],ignore_index=True)
case=pd.concat([pd.read_csv(x/'A03_CASE_LEVEL.csv') for x in paths],ignore_index=True)
tie=pd.concat([pd.read_csv(x/'A03_TIE_SENSITIVITY.csv') for x in paths],ignore_index=True)
primary=policy.query('budget==0.9').copy()
assert primary.cell_key.nunique()==80 and len(primary)==320
# CIs were exploratory per-cell and must not be interpreted as independent across shared datasets.
by_model=primary.groupby(['model_family','policy']).agg(
  cells=('cell_key','nunique'),mean_delta=('delta_risk_vs_confidence','mean'),
  median_delta=('delta_risk_vs_confidence','median'),
  improved=('delta_risk_vs_confidence',lambda s:(s< -1e-12).sum()),
  worsened=('delta_risk_vs_confidence',lambda s:(s>1e-12).sum()),
  tied=('delta_risk_vs_confidence',lambda s:(s.abs()<=1e-12).sum()),
  mean_accepted_risk=('accepted_risk','mean'),
  mean_reviewed_error_fraction=('recall_of_errors_reviewed','mean')).reset_index()
by_model.to_csv(out/'A03_BY_MODEL.csv',index=False)
by_domain=primary.groupby(['kind','policy']).agg(cells=('cell_key','nunique'),
  mean_delta=('delta_risk_vs_confidence','mean'),
  improved=('delta_risk_vs_confidence',lambda s:(s< -1e-12).sum()),
  worsened=('delta_risk_vs_confidence',lambda s:(s>1e-12).sum())).reset_index()
by_domain.to_csv(out/'A03_BY_DOMAIN_TYPE.csv',index=False)
by_budget=policy.groupby(['budget','policy']).agg(cells=('cell_key','nunique'),
 mean_delta=('delta_risk_vs_confidence','mean'),
 improved=('delta_risk_vs_confidence',lambda s:(s< -1e-12).sum()),
 worsened=('delta_risk_vs_confidence',lambda s:(s>1e-12).sum()),
 mean_risk=('accepted_risk','mean'),mean_coverage=('coverage','mean')).reset_index()
by_budget.to_csv(out/'A03_BY_BUDGET.csv',index=False)
# Stable reference cases vs high-confidence unstable cases. Pooled cases are repeated across models and splits:
# descriptive only, never binomial independent observations.
by_source=[]
for (split,model),frame in case.query("partition=='heldout'").groupby(['split_seed','model_family']):
    hi=frame.query('ref_confidence >= 0.9').copy()
    unstable=hi[hi.observed_agreement<.8];stable=hi[hi.observed_agreement>=.8]
    by_source.append(dict(split_seed=split,model_family=model,high_conf_n=len(hi),
          unstable_n=len(unstable),unstable_errors=int(unstable.reference_error.sum()),
          stable_n=len(stable),stable_errors=int(stable.reference_error.sum()),
          unstable_error_rate=(unstable.reference_error.mean() if len(unstable) else np.nan),
          stable_error_rate=(stable.reference_error.mean() if len(stable) else np.nan)))
pd.DataFrame(by_source).to_csv(out/'A03_INSTABILITY_ERROR_ENRICHMENT.csv',index=False)
# Tie variability per cell and policy: two methods may have different tie groups.
variability=tie.groupby(['cell_key','policy']).agg(
 delta_min=('delta_risk_vs_confidence','min'),delta_max=('delta_risk_vs_confidence','max'),
 delta_std=('delta_risk_vs_confidence','std'),
 risk_min=('accepted_risk','min'),risk_max=('accepted_risk','max')).reset_index()
variability.to_csv(out/'A03_TIE_VARIABILITY.csv',index=False)
# Deterministic failure cases on the same 90% review budget. Do not inspect or modify masks for optimization.
# Choose 4 example dataset-model pairs with positive and negative deltas.
sub=primary.query("policy=='combined_fixed'").sort_values(['delta_risk_vs_confidence','cell_key'])
selected=pd.concat([sub.head(5),sub.tail(5)]).drop_duplicates('cell_key')
selected.to_csv(out/'A03_TOP_SUCCESS_AND_FAILURE_CELLS.csv',index=False)
summary={
 'protocol':'A03 held-out, exact budgeted selective review',
 'experiment_cells':int(primary.cell_key.nunique()),
 'trainings':int(primary.cell_key.nunique()*31),
 'validation_and_heldout_case_rows':len(case),
 'test_case_model_rows':int(len(case[case.partition=='heldout'])),
 'dataset_regimes':sorted(set(primary.dataset)),
 'models':sorted(set(primary.model_family)),
 'budget_list':sorted(set(policy.budget)),
 'primary_budget':0.9,
 'by_policy':{k:{'mean_delta':float(v.delta_risk_vs_confidence.mean()),
         'improved_cells':int((v.delta_risk_vs_confidence< -1e-12).sum()),
         'worsened_cells':int((v.delta_risk_vs_confidence>1e-12).sum()),
         'tied_cells':int((v.delta_risk_vs_confidence.abs()<=1e-12).sum()),
         'median_delta':float(v.delta_risk_vs_confidence.median())}
              for k,v in primary.groupby('policy')},
 'no_universal_superiority':True,
 'interpretation':"Exploratory, correlated cells; significance cannot be inferred from pooled outcomes. Exact matched coverage is an unlabeled batch-ranking evaluation."
}
(out/'A03_FINAL_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
