from __future__ import annotations
import json
from research.s03_explanation_validation.corruptions import corrupt_contract
from research.s03_explanation_validation.run_synthetic_smoke import smoke
from ruflex.domain.evidence import ExplanationContract,FeatureAttribution

def _clean(): return ExplanationContract(run_id='00000000-0000-0000-0000-000000000001',model_kind='logistic_regression',model_artifact_sha256='a'*64,preprocessing_identity='p',sample_identity='s',reference_identity='r',sample={'x':1.},target='target',prediction=.7,reference_definition='train reference',attributions=[FeatureAttribution(feature='x',observed_value=1.,reference_value=0.,attribution=.2)])
def test_s03_corruption_is_deterministic_and_one_component():
 a,changed=corrupt_contract(_clean(),family='M1_MODEL_MISMATCH',subtype='artifact_sha_swap',severity='NONE',seed=3);b,_=corrupt_contract(_clean(),family='M1_MODEL_MISMATCH',subtype='artifact_sha_swap',severity='NONE',seed=99)
 assert changed==['model_artifact_sha256'] and a.model_artifact_sha256==b.model_artifact_sha256=='0'*64
def test_s03_synthetic_native_product_smoke():
 result=smoke();assert result['empirical_s03_evidence'] is False;assert result['clean_status']=='PASSED_AVAILABLE_CHECKS';assert result['corrupt_status']=='FAILED';assert result['localized_model_identity'];assert result['reopen_status']=='FAILED'
