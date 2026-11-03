from pathlib import Path
import pandas as pd
import numpy as np
from a03_heldout import review_mask
root=Path(__file__).parents[1]
selected=[('breast_cancer_malignant','decision_tree',202),('synthetic_sep0.5_noise0.01','extra_trees',202),('synthetic_sep0.5_noise0.15','sgd_log_loss',202),('digits_5_to_9','decision_tree',202)]
rows=[]
for d,f,split in selected:
    data=pd.read_csv(root/'results'/f'split{split}'/'A03_CASE_LEVEL.csv')
    q=data[(data.dataset==d)&(data.model_family==f)&(data.partition=='heldout')].copy().reset_index(drop=True)
    ids=q.case_id.to_numpy()
    a=review_mask(q.score_confidence_only.to_numpy(),ids,.9,0)
    b=review_mask(q.score_combined_fixed.to_numpy(),ids,.9,0)
    err=q.reference_error.to_numpy().astype(bool)
    for idx,x in q.iterrows():
        if a[idx]!=b[idx] and x.reference_error:
            rows.append(dict(cell=f'{d}::{f}::split{split}',case_id=int(x.case_id),truth=int(x.truth),reference_prediction=int(x.reference_prediction),ref_confidence=x.ref_confidence,observed_agreement=x.observed_agreement,baseline_review=int(a[idx]),combined_review=int(b[idx]),error=int(err[idx])))
    print(d,f,split,'errors reviewed conf',int((a&err).sum()),'combined',int((b&err).sum()),'delta',(int((a&err).sum())-int((b&err).sum()))/(len(q)-int(a.sum())))
fail=pd.DataFrame(rows);fail.to_csv(root/'results'/'analysis'/'A03_POLICY_SWITCH_FAILURE_CASES.csv',index=False)
print(fail.head(25).to_string(index=False))
