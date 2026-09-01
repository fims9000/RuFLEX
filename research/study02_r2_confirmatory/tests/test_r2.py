import json
from pathlib import Path
import pytest
from research.study02_r2_confirmatory import scripts
ROOT=Path(__file__).resolve().parents[1]
def test_plan_materializes_actual_distinct_inputs_and_pairs_share_base():
 scripts.freeze();result=scripts.validate();assert result['pairs']==40 and result['distinct_inputs']==40
def test_no_authorization_refuses(tmp_path,monkeypatch):
 scripts.freeze();monkeypatch.setattr(scripts,'AUTH',tmp_path/'missing.json')
 with pytest.raises(scripts.Refusal):scripts.gate()
@pytest.mark.parametrize('field',('product_sha','protocol_sha','manifest_id','plan_sha'))
def test_wrong_external_authorization_identity_refuses(tmp_path,monkeypatch,field):
 manifest=scripts.freeze();record={'authorization_status':'AUTHORIZED','product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'plan_sha':manifest['plan_sha']};record[field]='wrong';path=tmp_path/'auth.json';path.write_text(json.dumps(record));monkeypatch.setattr(scripts,'AUTH',path)
 with pytest.raises(scripts.Refusal):scripts.gate()
def test_matching_external_authorization_passes_without_mutating_frozen_files(tmp_path,monkeypatch):
 manifest=scripts.freeze();manifest_path=ROOT/'config/locked_manifest.json';plan_path=ROOT/'config/locked_execution_plan.jsonl';before=(manifest_path.read_bytes(),plan_path.read_bytes())
 record={'authorization_status':'AUTHORIZED','product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'plan_sha':manifest['plan_sha']};path=tmp_path/'auth.json';path.write_text(json.dumps(record));monkeypatch.setattr(scripts,'AUTH',path)
 assert scripts.gate()['manifest_id']==manifest['manifest_id'] and before==(manifest_path.read_bytes(),plan_path.read_bytes())
@pytest.mark.parametrize('frozen_file',('core.py','scripts.py','PROTOCOL.md','config/locked_execution_plan.jsonl'))
def test_modified_frozen_file_identity_refuses(monkeypatch,frozen_file):
 scripts.freeze();original=scripts.sha
 def altered(path):return '0'*64 if str(path).endswith(frozen_file) else original(path)
 monkeypatch.setattr(scripts,'sha',altered)
 with pytest.raises(scripts.Refusal):scripts.verify_frozen_identity()
def test_modified_manifest_identity_refuses(monkeypatch):
 scripts.freeze();original=scripts.load
 def altered():
  manifest,rows=original();manifest['pairs']=999;return manifest,rows
 monkeypatch.setattr(scripts,'load',altered)
 with pytest.raises(scripts.Refusal):scripts.verify_frozen_identity()
@pytest.mark.parametrize('field',('execution_contract_hash','product_sha','protocol_sha','manifest_id','execution_plan_sha'))
def test_wrong_frozen_result_row_binding_fails(field):
 manifest=scripts.freeze();_,plans=scripts.load();expected=scripts.expected_result_mapping(plans);scenario=plans[0]['clean_contract']['scenario_id'];row={**expected[scenario],'scenario_id':scenario,'product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'execution_plan_sha':manifest['plan_sha']};row[field]='wrong'
 with pytest.raises(AssertionError):scripts.validate_result_row(row,expected,manifest)
def test_wrong_clean_or_corrupt_semantics_and_duplicate_rows_fail():
 manifest=scripts.freeze();_,plans=scripts.load();expected=scripts.expected_result_mapping(plans);clean=next(key for key,value in expected.items() if value['clean_or_corrupt']=='clean');corrupt=next(key for key,value in expected.items() if value['clean_or_corrupt']=='corrupt')
 clean_row={**expected[clean],'scenario_id':clean,'product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'execution_plan_sha':manifest['plan_sha'],'attempted_source_type':'AnalysisEvaluation','artifact_created':True,'product_outcome':'WRONG'}
 with pytest.raises(AssertionError):scripts.validate_observed_semantics(clean_row)
 corrupt_row={**expected[corrupt],'scenario_id':corrupt,'product_sha':manifest['product_sha'],'protocol_sha':manifest['protocol_sha'],'manifest_id':manifest['manifest_id'],'execution_plan_sha':manifest['plan_sha'],'attempted_source_type':'FinalTestEvaluation','final_test_artifact_exists':True,'final_test_artifact_type':'FinalTestEvaluation','attempted_source_id':'same','final_test_id':'same','product_outcome':'WRONG','invalid_artifact_persisted':False}
 with pytest.raises(AssertionError):scripts.validate_observed_semantics(corrupt_row)
 with pytest.raises(AssertionError):scripts.validate_result_set([clean_row]*80,expected,manifest)
def test_dev_final_test_is_real_and_corrupt_uses_exact_id():
 rows=scripts.dev();corrupt=[x for x in rows if x['clean_or_corrupt']=='corrupt'];assert len(corrupt)==2
 assert all(x['final_test_artifact_exists'] and x['final_test_artifact_type']=='FinalTestEvaluation' and x['attempted_source_id']==x['final_test_id'] and x['attempted_source_type']=='FinalTestEvaluation' for x in corrupt)
 assert all(x['product_outcome']=='PREVENTED_BY_VALIDATION_ONLY_ARTIFACT_INTERFACE' and x['exception_type']=='FileNotFoundError' and 'analyses/evaluations' in x['exception_message'] for x in corrupt)
