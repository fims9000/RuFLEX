"""Synthetic-only native S03 conformance. Never reads S03 benchmark data."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.evidence import (check_explanation, create_gradient_shap_explanation, create_integrated_gradients_explanation, create_occlusion_explanation, create_permutation_shap_explanation, create_tree_shap_explanation, load_explanation_check, predict_run_sample)
from ruflex.application.training import train_model
from research.s03_explanation_validation.corruptions import corrupt_contract

ROOT=Path(__file__).resolve().parent; CONFIG=ROOT/"config"

def _persist(root: Path, explanation):
    path=root/"evidence"/"explanations"; path.mkdir(parents=True,exist_ok=True); (path/f"{explanation.explanation_id}.json").write_text(explanation.model_dump_json(indent=2)); return explanation

def _frame() -> pd.DataFrame:
    return pd.DataFrame([{"x1":float(i%11),"x2":float((i*3)%13),"x3":float((i*5)%17),"x4":float((i*7)%19),"target":int((i%11)+((i*3)%13) > 11)} for i in range(96)])

def run() -> dict:
  with tempfile.TemporaryDirectory(prefix="ruflex-s03-native-") as temp:
    root=Path(temp); frame=_frame(); raw=frame.to_csv(index=False).encode(); artifact=persist_dataset_bytes(root,raw); profile=inspect_dataset(frame,source_artifact_sha256=artifact.sha256); contract=build_dataset_contract(profile,target="target",task="binary_classification"); persist_dataset_contract(root,contract,run_data_audit(contract,frame),profile)
    base={"seed":3003,"split_seed":3003,"training_seed":3003,"validation_fraction":.2,"test_fraction":.2}
    runs={"logistic_regression":train_model(root,model_kind="logistic_regression",**base),"decision_tree":train_model(root,model_kind="decision_tree",**base),"random_forest":train_model(root,model_kind="random_forest",**base),"gradient_boosting":train_model(root,model_kind="gradient_boosting",learning_rate=.1,**base),"flat_neuro_fuzzy":train_model(root,model_kind="flat_neuro_fuzzy",max_epochs=3,batch_size=16,patience=2,max_rules=4,learning_rate=.01,**base)}
    # A second persisted logistic run is an existing deterministic alternate for M1b.
    alternate=train_model(root,model_kind="logistic_regression",seed=3004,split_seed=3003,training_seed=3004,validation_fraction=.2,test_fraction=.2)
    sample={"x1":5.,"x2":2.,"x3":8.,"x4":3.}
    clean=create_occlusion_explanation(root,runs["logistic_regression"].run_id,sample)
    outcomes=[]
    cases=[("M1_MODEL_MISMATCH","artifact_sha_swap","NONE"),("M1_MODEL_MISMATCH","run_identity_swap","NONE"),("P1_PREPROCESSING_MISMATCH","preprocessing_identity_swap","NONE"),("P1_PREPROCESSING_MISMATCH","feature_order_identity_swap","NONE"),("S1_SAMPLE_TARGET_MISMATCH","sample_identity_swap","NONE"),("S1_SAMPLE_TARGET_MISMATCH","target_identity_swap","NONE"),("R1_REFERENCE_BACKGROUND_MISMATCH","reference_identity_swap","NONE")]
    for subtype in ("additive_noise","sign_flip","permutation"):
      cases.extend(("A1_ATTRIBUTION_MUTATION",subtype,s) for s in ("LOW","MEDIUM","HIGH"))
    cases.extend(("ADV_EXPLAINER_AWARE","structurally_valid_attribution_permutation",s) for s in ("LOW","MEDIUM","HIGH"))
    for family,subtype,severity in cases:
      corrupt,changed=corrupt_contract(clean,family=family,subtype=subtype,severity=severity,seed=3003,alternate_run_id=alternate.run_id); _persist(root,corrupt); checked=check_explanation(root,corrupt.explanation_id); reopened=load_explanation_check(root,checked.check_id)
      outcomes.append({"family":family,"subtype":subtype,"severity":severity,"changed_fields":changed,"status":checked.status,"reopen_status":reopened.status,"model_identity_failed":any(i.name=="model_identity" and i.status=="FAIL" for i in checked.checks),"unhandled_exception":False})
    l1=[]
    for explainer,build,kwargs in (("integrated_gradients",create_integrated_gradients_explanation,{"steps":64}),("gradient_shap",create_gradient_shap_explanation,{"background_count":24}),("permutation_shap",create_permutation_shap_explanation,{"background_count":24}),("tree_shap",create_tree_shap_explanation,{"background_count":32})):
      run=runs["flat_neuro_fuzzy"] if explainer in {"integrated_gradients","gradient_shap"} else (runs["logistic_regression"] if explainer=="permutation_shap" else runs["decision_tree"])
      clean_explanation=build(root,run.run_id,sample,**kwargs); clean_check=check_explanation(root,clean_explanation.explanation_id)
      levels=[]
      for severity, reduced in (("LOW", {k:(61 if k=="steps" else 23) for k in kwargs}), ("MEDIUM", {k:(48 if k=="steps" else 18) for k in kwargs}), ("HIGH", {k:(16 if k=="steps" else 8) for k in kwargs})):
        reduced_explanation=build(root,run.run_id,sample,**reduced); checked=check_explanation(root,reduced_explanation.explanation_id); reopen=load_explanation_check(root,checked.check_id); levels.append({"severity":severity,"parameters":reduced,"status":checked.status,"reopen_status":reopen.status})
      l1.append({"explainer":explainer,"clean_status":clean_check.status,"levels":levels,"fresh_native_generation":True})
    result={"schema_version":1,"study":"S03_SYNTHETIC_NATIVE_E2E_ONLY","benchmark_results_seen":False,"benchmark_explanations_generated":False,"scientific_outcomes_seen":False,"subtype_outcomes":outcomes,"l1_outcomes":l1,"run_count":len(runs)+1}
    (CONFIG/"synthetic_native_e2e_receipt.json").write_text(json.dumps(result,sort_keys=True,separators=(",",":"))+"\n")
    return result

if __name__=="__main__": print(json.dumps(run(),sort_keys=True))
