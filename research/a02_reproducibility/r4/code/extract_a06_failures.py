"""Extract factual cross-policy switches from frozen A06 heldout outputs."""
from pathlib import Path
import pandas as pd
import numpy as np
from a06_streaming import batch_reject

ROOT=Path(__file__).resolve().parent.parent
parts=[]
for nm in ['fair','randhie','modechoice','anes']:
    q=pd.read_csv(ROOT/'results'/nm/'A06_CASE_LEVEL.csv',float_precision='round_trip')
    parts.append(q[q.partition=='heldout'])
raw=pd.concat(parts,ignore_index=True)
rows=[]
for cell,g in raw.groupby('cell'):
    g=g.sort_values('case_id')
    ids=g.case_id.to_numpy(dtype=int)
    b=batch_reject(g.score_confidence_only.to_numpy(dtype=float),ids,.9,1)
    c=batch_reject(g.score_combined_fixed.to_numpy(dtype=float),ids,.9,1)
    errs=(g.truth.to_numpy()!=g.prediction.to_numpy())
    for i,r in enumerate(g.itertuples(index=False)):
        if b[i]==c[i]: continue
        if (b[i] and not c[i] and errs[i]): kind='LOST_ERROR_CAPTURE'
        elif (c[i] and not b[i] and errs[i]):kind='GAINED_ERROR_CAPTURE'
        elif (b[i] and not c[i]):kind='LOST_REVIEW_OF_CORRECT'
        else:kind='GAINED_REVIEW_OF_CORRECT'
        rows.append({'cell':cell,'case_id':r.case_id,'truth':r.truth,'reference_prediction':r.prediction,
             'confidence':r.confidence,'reference_agreement':r.agreement,
             'score_confidence':r.score_confidence_only,'score_combined':r.score_combined_fixed,
             'kind':kind})
out=pd.DataFrame(rows)
out.to_csv(ROOT/'results'/'analysis'/'A06_POLICY_SWITCHES.csv',index=False)
for cell in ['fair_affair_any::sgd_log_loss::split303','randhie_doctor_visit_any::sgd_log_loss::split404','modechoice_alternative_selected::decision_tree::split404']:
 d=out[(out.cell==cell)&(out.kind=='LOST_ERROR_CAPTURE')]
 print(cell,'lost',len(d))
 print(d.head(2)[['case_id','truth','reference_prediction','confidence','reference_agreement']].to_string(index=False))
