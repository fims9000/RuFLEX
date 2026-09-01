from __future__ import annotations
import json
from pathlib import Path
from research.study02_protocol_integrity.core.pair_diff import semantic_pair_diff
from research.study02_protocol_integrity.core.execution_contract import contract_for
from research.study02_protocol_integrity.core.scenario_materialization import materialize_plan
from research.study02_protocol_integrity.generators import iid_tabular,grouped_tabular,temporal
ROOT=Path(__file__).resolve().parents[1]
def main():
 matrix=json.loads((ROOT/'config/detectability_matrix.json').read_text()); rows=[]
 for family in [x for x in matrix if x['status']=='SUPPORTED_PREVENTABLE']:
  for index in range(20):
   seed=20260902+index; generator={'V01':iid_tabular,'V06':grouped_tabular,'V07':temporal}[family['id']]; base={'pair_id':f"{family['id']}-{index:02d}",'generator_family':generator.generate(seed)['family'],'seed':seed,'generator_parameters':generator.generate(seed)}
   clean={**base,'protocol_mutation':None}; corrupt={**base,'protocol_mutation':{'family':family['id'],'stage':family['stage'],'severity':'BLOCK'}}; diff=semantic_pair_diff(clean,corrupt,family['id'])
   clean_id=base['pair_id']+'-clean'; corrupt_id=base['pair_id']+'-corrupt'
   materialized=materialize_plan({**base,'generator_family':base['generator_family']})
   clean_contract=contract_for(pair_id=base['pair_id'],scenario_id=clean_id,family=family['id'],role='clean',generator_family=base['generator_family'],generator_parameters=base['generator_parameters'],seed=seed,base_input_hash=materialized.input_hash)
   corrupt_contract=contract_for(pair_id=base['pair_id'],scenario_id=corrupt_id,family=family['id'],role='corrupt',generator_family=base['generator_family'],generator_parameters=base['generator_parameters'],seed=seed,base_input_hash=materialized.input_hash)
   rows.append({'pair_id':base['pair_id'],'family':family['id'],'clean_scenario_id':clean_id,'corrupt_scenario_id':corrupt_id,'violation_family':family['id'],**base,'mutation_parameters':corrupt['protocol_mutation'],'base_scenario_hash':diff['pair_base_hash'],'base_input_hash':materialized.input_hash,'clean_input_hash':materialized.input_hash,'corrupt_input_hash':materialized.input_hash,'clean_spec_hash':diff['clean_spec_hash'],'corrupt_spec_hash':diff['corrupt_spec_hash'],'expected_stage':family['stage'],'expected_severity':'BLOCK','detectability_status':family['status'], 'clean_execution_contract':clean_contract.payload(), 'corrupt_execution_contract':corrupt_contract.payload(), 'clean_execution_contract_hash':clean_contract.contract_hash, 'corrupt_execution_contract_hash':corrupt_contract.contract_hash, 'actual_product_entrypoint':clean_contract.expected_product_entrypoint, 'baseline_plan':{'entrypoint':'research.study02_protocol_integrity.baselines.basic_manifest_audit.audit','ruleset':'basic-manifest-audit-v1'}, 'persistence_plan':{'required':True,'method':'save_close_reopen'}, 'expected_artifact_type':clean_contract.artifact_type_expected, 'expected_clean_semantic_status':'ALLOWED_VALID', 'expected_corrupt_semantic_class':corrupt_contract.expected_semantic_outcome})
 out=ROOT/'config/locked_scenarios.jsonl';out.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
 diagnostics=ROOT/'artifacts/diagnostics/locked_pair_diffs.jsonl';diagnostics.write_text(''.join(json.dumps({'pair_id':r['pair_id'],'primary_family':r['violation_family'],'base_scenario_hash':r['base_scenario_hash'],'clean_spec_hash':r['clean_spec_hash'],'corrupt_spec_hash':r['corrupt_spec_hash'],'changed_field':'protocol_mutation'},sort_keys=True)+'\n' for r in rows));print(json.dumps({'pairs':len(rows),'scenarios':len(rows)*2}))
 materialized=ROOT/'artifacts/diagnostics/materialized_scenarios.jsonl'; materialized.write_text(''.join(json.dumps({'pair_id':r['pair_id'],'generator_family':r['generator_family'],'seed':r['seed'],'generator_parameters':r['generator_parameters'],'base_input_hash':r['base_input_hash'],'clean_input_hash':r['clean_input_hash'],'corrupt_input_hash':r['corrupt_input_hash'],'clean_execution_contract_hash':r['clean_execution_contract_hash'],'corrupt_execution_contract_hash':r['corrupt_execution_contract_hash']},sort_keys=True)+'\n' for r in rows))
 plan=ROOT/'artifacts/manifests/locked_execution_plan.jsonl'; plan.parent.mkdir(parents=True,exist_ok=True); plan.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows)); print(json.dumps({'pairs':len(rows),'scenarios':len(rows)*2,'plan':str(plan)}))
if __name__=='__main__':main()
