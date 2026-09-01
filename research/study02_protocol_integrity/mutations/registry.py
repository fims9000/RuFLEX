from __future__ import annotations
MARKERS={'V01':('preprocessing_fit_scope','train_test'),'V02':('group_overlap',True),'V03':('temporal_future_used',True),'V04':('target_feature_lineage',True),'V05':('final_test_role_used',True),'V06':('threshold_fit_scope','test'),'V07':('calibration_fit_scope','test'),'V08':('best_seed_final_test',True),'V09':('evidence_hash_mismatch',True),'V10':('sample_identity_mismatch',True)}
def mutate(base:dict, family:str)->dict:
 if family not in MARKERS: raise ValueError(family)
 result=dict(base); key,value=MARKERS[family]; result[key]=value; result['_primary_violation']=family; return result
def validate_one_violation(state:dict, expected:str|None)->None:
 found=[key for key,_ in MARKERS.values() if key in state]
 if expected is None and found: raise ValueError('clean scenario contains corruption')
 if expected is not None and found != [MARKERS[expected][0]]: raise ValueError(f'one-violation invariant: {found}')
