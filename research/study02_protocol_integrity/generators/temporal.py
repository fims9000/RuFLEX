from __future__ import annotations
def generate(seed:int)->dict:
 return {'family':'temporal','seed':seed,'sample_count':100+seed%51,'feature_count':4+seed%6,'class_imbalance':round(.2+(seed%20)/100,2),'group_count':0,'temporal_drift':round(.1+(seed%50)/100,2)}
