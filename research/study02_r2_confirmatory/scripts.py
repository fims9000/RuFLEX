from __future__ import annotations
import argparse,hashlib,json,tempfile
from pathlib import Path
from research.study02_r2_confirmatory.core import PRODUCT_SHA,Contract,digest,execute,materialize,parameters
ROOT=Path(__file__).resolve().parent; PLAN=ROOT/'config/locked_execution_plan.jsonl'; MANIFEST=ROOT/'config/locked_manifest.json'; AUTH=ROOT.parents[1]/'.agent-state/STUDY02_R2_TEST_AUTHORIZATION.json'; RAW=ROOT/'artifacts/raw/locked_outcomes.jsonl'
def generate():
 rows=[]
 for family in ('V06','V07'):
  for index in range(20):
   seed=20261101+index;pair_id=f'R2-{family}-{index:02d}';base={'pair_id':pair_id,'family':family,'seed':seed,'generator_family':'iid' if family=='V06' else 'temporal','generator_parameters':parameters(family,seed)};_,input_hash,data_content_sha256=materialize(base)
   entry='ruflex.application.training.select_validation_threshold' if family=='V06' else 'ruflex.application.training.fit_validation_calibration'
   clean=Contract(pair_id,pair_id+'-clean',family,'clean',seed,base['generator_family'],base['generator_parameters'],input_hash,entry);corrupt=Contract(pair_id,pair_id+'-corrupt',family,'corrupt',seed,base['generator_family'],base['generator_parameters'],input_hash,entry)
   rows.append({**base,'base_input_hash':input_hash,'data_content_sha256':data_content_sha256,'clean_input_hash':input_hash,'corrupt_input_hash':input_hash,'clean_contract':clean.payload(),'corrupt_contract':corrupt.payload(),'clean_contract_hash':clean.hash(),'corrupt_contract_hash':corrupt.hash(),'expected_clean':'ALLOWED_VALID','expected_corrupt':'PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE'})
 PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows));return rows
def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def freeze():
 rows=generate();files=['PROTOCOL.md','DECISIONS.md','core.py','scripts.py','config/locked_execution_plan.jsonl'];hashes={name:sha(ROOT/name) for name in files};protocol=digest(hashes);manifest={'schema_version':2,'study':'Study 02 R2 confirmatory','product_sha':PRODUCT_SHA,'protocol_sha':protocol,'plan_sha':sha(PLAN),'file_hashes':hashes,'families':['V06','V07'],'pairs':len(rows),'scenarios':len(rows)*2,'authorization_record_path':'.agent-state/STUDY02_R2_TEST_AUTHORIZATION.json','authorization_external':True};manifest['manifest_id']=digest(manifest);MANIFEST.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');return manifest
def load():return json.loads(MANIFEST.read_text()),[json.loads(x) for x in PLAN.read_text().splitlines()]
class Refusal(RuntimeError):pass
def verify_frozen_identity():
 manifest,_=load();actual={name:sha(ROOT/name) for name in manifest['file_hashes']}
 if actual!=manifest['file_hashes']:raise Refusal('Frozen R2 code/protocol/plan identity differs from manifest.')
 if digest(actual)!=manifest['protocol_sha'] or sha(PLAN)!=manifest['plan_sha']:raise Refusal('Frozen R2 protocol or execution-plan identity differs.')
 if digest({key:value for key,value in manifest.items() if key!='manifest_id'})!=manifest['manifest_id']:raise Refusal('Frozen R2 manifest identity differs.')
 product=ROOT.parents[1]/'release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip'
 if sha(product)!=manifest['product_sha'] or manifest['product_sha']!=PRODUCT_SHA:raise Refusal('Frozen Product V1.0.1 identity differs.')
 return {'status':'PASS','product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'plan_sha':manifest['plan_sha']}
def gate():
 verified=verify_frozen_identity();manifest,_=load()
 if not AUTH.exists():raise Refusal('R2 is not externally authorized.')
 auth=json.loads(AUTH.read_text());expected={'product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'plan_sha':manifest['plan_sha']}
 if auth.get('authorization_status')!='AUTHORIZED' or any(auth.get(k)!=v for k,v in expected.items()):raise Refusal('R2 authorization does not match frozen identities.')
 return {**expected,'frozen_identity':'PASS'}
def validate():
 manifest,rows=load();assert len(rows)==40 and {x['family'] for x in rows}=={'V06','V07'} and all(sum(x['family']==f for x in rows)==20 for f in ('V06','V07'));hashes=[]
 for row in rows:
  _,value,data_content=materialize(row);clean=Contract(**row['clean_contract']);corrupt=Contract(**row['corrupt_contract']);assert value==row['base_input_hash']==row['clean_input_hash']==row['corrupt_input_hash']==clean.base_input_hash==corrupt.base_input_hash;assert data_content==row['data_content_sha256'];assert clean.seed==row['seed']==corrupt.seed and clean.generator_parameters==row['generator_parameters'];hashes.append(value)
 assert len(set(hashes))==40 and len({row['data_content_sha256'] for row in rows})==40 and sha(PLAN)==manifest['plan_sha'];return {'status':'PASS','pairs':40,'scenarios':80,'distinct_inputs':len(set(hashes)),'distinct_data_content_hashes':len({row['data_content_sha256'] for row in rows}),'plan_sha':sha(PLAN)}
def run():
 verify_frozen_identity();gate();validate();manifest,rows=load();RAW.parent.mkdir(parents=True,exist_ok=True);existing={json.loads(x)['scenario_id'] for x in RAW.read_text().splitlines()} if RAW.exists() else set();emitted=0
 with RAW.open('a') as handle:
  for row in rows:
   for key in ('clean_contract','corrupt_contract'):
    contract=Contract(**row[key])
    if contract.scenario_id in existing:continue
    result=execute(contract,row,RAW.parent/'projects'/contract.scenario_id);result.update(product_sha=manifest['product_sha'],protocol_sha=manifest['protocol_sha'],manifest_id=manifest['manifest_id'],execution_plan_sha=manifest['plan_sha']);handle.write(json.dumps(result,sort_keys=True)+'\n');handle.flush();emitted+=1
 return {'status':'PASS','emitted':emitted,'raw':str(RAW)}
def expected_result_mapping(plans:list[dict])->dict:
 expected={}
 for plan in plans:
  for role,key in [('clean','clean_contract'),('corrupt','corrupt_contract')]:expected[plan[key]['scenario_id']]={'pair_id':plan['pair_id'],'clean_or_corrupt':role,'family':plan['family'],'seed':plan['seed'],'generator_parameters':plan['generator_parameters'],'base_input_hash':plan['base_input_hash'],'data_content_sha256':plan['data_content_sha256'],'execution_contract_hash':plan[key+'_hash']}
 return expected
def validate_result_row(row:dict,expected:dict,manifest:dict):
 assert row['scenario_id'] in expected;assert all(row[key]==value for key,value in expected[row['scenario_id']].items());assert row['product_sha']==manifest['product_sha'] and row['protocol_sha']==manifest['protocol_sha'] and row['manifest_id']==manifest['manifest_id'] and row['execution_plan_sha']==manifest['plan_sha']
def validate_observed_semantics(row:dict):
 if row['clean_or_corrupt']=='clean':assert row['attempted_source_type']=='AnalysisEvaluation' and row['artifact_created'] and row['product_outcome']=='ALLOWED_VALID'
 else:assert row['final_test_artifact_exists'] and row['final_test_artifact_type']=='FinalTestEvaluation' and row['attempted_source_id']==row['final_test_id'] and row['attempted_source_type']=='FinalTestEvaluation' and row['product_outcome']=='PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE' and not row['invalid_artifact_persisted']
def validate_result_set(rows:list[dict],expected:dict,manifest:dict):
 assert len(rows)==len(expected)==80 and {row['scenario_id'] for row in rows}==set(expected)
 for row in rows:validate_result_row(row,expected,manifest);validate_observed_semantics(row)
def validate_locked_results():
 verify_frozen_identity();manifest,plans=load();rows=[json.loads(x) for x in RAW.read_text().splitlines()];assert len(rows)==80==len({x['scenario_id'] for x in rows}) and len({x['base_input_hash'] for x in rows})==40
 expected=expected_result_mapping(plans)
 validate_result_set(rows,expected,manifest)
 corrupt=[x for x in rows if x['clean_or_corrupt']=='corrupt'];clean=[x for x in rows if x['clean_or_corrupt']=='clean']
 assert {f:sum(x['family']==f and x['clean_or_corrupt']=='clean' for x in rows) for f in ('V06','V07')}=={'V06':20,'V07':20} and {f:sum(x['family']==f and x['clean_or_corrupt']=='corrupt' for x in rows) for f in ('V06','V07')}=={'V06':20,'V07':20}
 return {'status':'PASS','rows':len(rows),'corrupt':len(corrupt),'clean':len(clean)}
def dev():
 rows=generate()[:1]+[x for x in generate() if x['family']=='V07'][:1];out=[]
 with tempfile.TemporaryDirectory() as temp:
  for row in rows:
   for key in ('clean_contract','corrupt_contract'):out.append(execute(Contract(**row[key]),row,Path(temp)/row[key]['scenario_id']))
 (ROOT/'artifacts/dev.json').parent.mkdir(parents=True,exist_ok=True);(ROOT/'artifacts/dev.json').write_text(json.dumps(out,indent=2)+'\n');return out
def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','validate','dev','locked','gate','verify','validate-locked']);a=p.parse_args();fn={'freeze':freeze,'validate':validate,'dev':dev,'locked':run,'gate':gate,'verify':verify_frozen_identity,'validate-locked':validate_locked_results}[a.command];print(json.dumps(fn(),sort_keys=True,default=str))
if __name__=='__main__':main()
