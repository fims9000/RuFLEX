"""Frozen independently specified, intentionally minimal manifest audit.

It consumes only the declared execution-plan metadata, never RuFLEX services.
"""
def audit(state:dict)->list[dict]:
 alerts=[]
 for key,stage in [('sample_overlap','SPLIT'),('group_overlap','SPLIT'),('final_test_role_used','MODEL_SELECTION'),('evidence_hash_mismatch','EVIDENCE_LINEAGE')]:
  if state.get(key): alerts.append({'family':key,'stage':stage,'severity':'BLOCK'})
 return alerts
