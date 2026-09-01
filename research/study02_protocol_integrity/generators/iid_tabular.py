from __future__ import annotations
def generate(seed:int)->dict:
 return {'family':'iid','seed':seed,'sample_count':80+seed%41,'feature_count':4+seed%5,'class_imbalance':round(.15+(seed%30)/100,2),'group_count':0,'temporal_drift':0.0}
