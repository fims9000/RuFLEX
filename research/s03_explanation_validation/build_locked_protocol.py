"""Build S03 Phase 0 frozen plan; this script never trains or evaluates a benchmark."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent; C=ROOT/'config'
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 matrix=json.loads((C/'matrix.json').read_text()); corrupt=json.loads((C/'corruption_spec.json').read_text()); rows=[]
 for dataset in matrix['datasets']:
  for model, explainers in matrix['models'].items():
   for explainer in explainers:
    for sample in range(matrix['samples_per_dataset_model']):
     for family,detail in corrupt['families'].items():
      subtypes=detail.get('subtypes',['clean']); severities=detail.get('severity_levels',['NONE'])
      for subtype in subtypes:
       for severity in severities:
        for mode in matrix['validators']:
         row={'execution_id':hashlib.sha256(canon([dataset,model,explainer,sample,family,subtype,severity,mode,0]).encode()).hexdigest()[:20],'dataset_id':dataset,'model_family':model,'explainer':explainer,'sample_slot':sample,'failure_family':family,'failure_subtype':subtype,'severity':severity,'validator_mode':mode,'repeat_identity':0,'expected_mechanism':'product ExplanationCheck/replay' if family not in {'L1_LOW_FIDELITY','ADV_EXPLAINER_AWARE'} else 'applicable native metric/replay or NOT_AVAILABLE','benchmark_execution_forbidden':True}
         rows.append(row)
 plan=C/'locked_execution_plan.jsonl';plan.write_text(''.join(canon(r)+'\n' for r in rows))
 hashes={name:sha(C/name) for name in ('dataset_specs.json','matrix.json','corruption_spec.json','locked_execution_plan.jsonl')}
 hashes['protocol_sha256']=sha(ROOT/'PROTOCOL.md');hashes['statistical_plan_sha256']=sha(ROOT/'STATISTICAL_ANALYSIS_PLAN.md');payload={'schema_version':1,'study':'S03','status':'EXECUTABLE_PRE_FREEZE_NO_BENCHMARK_RESULTS','hashes':hashes,'matrix_rows':len(rows),'split_seed':3003}
 payload['manifest_id']=hashlib.sha256(canon(payload).encode()).hexdigest();(C/'phase0_manifest.json').write_text(canon(payload)+'\n');print(payload['manifest_id'],len(rows))
if __name__=='__main__':main()
