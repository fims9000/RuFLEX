from __future__ import annotations
def generate(seed:int)->dict:
 return {'family':'grouped','seed':seed,'sample_count':90+seed%31,'feature_count':5+seed%4,'class_imbalance':round(.2+(seed%25)/100,2),'group_count':6+seed%9,'temporal_drift':0.0}
