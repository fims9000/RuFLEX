"""Build S03 Phase 0.2 plans, including clean controls; no benchmark work."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"

def canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"))
def key(*parts: object) -> str: return hashlib.sha256(canonical(parts).encode()).hexdigest()[:24]
def severity_values(detail: dict) -> list[str]: return detail.get("severity_levels", ["NONE"])

def expected_component(family: str, subtype: str) -> str:
    return {("M1_MODEL_MISMATCH","artifact_sha_swap"):"model_identity",("M1_MODEL_MISMATCH","run_identity_swap"):"model_identity",("P1_PREPROCESSING_MISMATCH","preprocessing_identity_swap"):"preprocessing_identity",("P1_PREPROCESSING_MISMATCH","feature_order_identity_swap"):"feature_order_identity",("S1_SAMPLE_TARGET_MISMATCH","sample_identity_swap"):"sample_target_identity",("S1_SAMPLE_TARGET_MISMATCH","target_identity_swap"):"sample_target_identity",("R1_REFERENCE_BACKGROUND_MISMATCH","reference_identity_swap"):"reference_identity",("A1_ATTRIBUTION_MUTATION","additive_noise"):"repeatability",("A1_ATTRIBUTION_MUTATION","sign_flip"):"repeatability",("A1_ATTRIBUTION_MUTATION","permutation"):"repeatability",("L1_LOW_FIDELITY","reduced_budget"):"external_quantus_or_replay_integrity",("ADV_EXPLAINER_AWARE","structurally_valid_attribution_permutation"):"external_quantus_or_replay_integrity"}[(family, subtype)]

def effective(family: str, subtype: str, severity: str) -> dict:
    if severity == "NONE": return {"severity":"NONE"}
    fraction={"LOW":.05,"MEDIUM":.25,"HIGH":.75}[severity]
    if family=="A1_ATTRIBUTION_MUTATION" and subtype=="additive_noise": return {"severity":severity,"fraction":fraction,"delta_formula":"severity*max(max_abs_clean_attribution,1e-12)","rademacher_seeded":True}
    if family=="L1_LOW_FIDELITY": return {"severity":severity,"fraction":fraction,"budget_rule":"max(method_minimum,round(clean_budget*(1-severity)))"}
    return {"severity":severity,"fraction":fraction,"effective_k_rule":"max(2,min(n_features,ceil(severity*n_features)))","equivalent_effect":"NOT_APPLICABLE"}

def l1_state(explainer: str) -> tuple[str,str]:
    return ("NOT_APPLICABLE","No meaningful computational fidelity knob for exact occlusion.") if explainer=="occlusion" else ("APPLICABLE","Fresh product-native reduced-budget explanation.")

def components(explainer: str, family: str, subtype: str, mode: str, quantus_state: str) -> list[dict]:
    selected={"IDENTITY_ONLY":{"IDENTITY"},"METRIC_ONLY":{"REPLAY_INTEGRITY","NATIVE_NUMERICAL","EXTERNAL_QUANTUS"},"COMBINED":{"IDENTITY","REPLAY_INTEGRITY","NATIVE_NUMERICAL","EXTERNAL_QUANTUS"}}[mode]
    out=[]
    for component in ("model_identity","preprocessing_identity","feature_order_identity","sample_target_identity","reference_identity"):
        out.append({"component":component,"state":"APPLICABLE" if "IDENTITY" in selected else "NOT_APPLICABLE","reason":"identity component is excluded from mode" if "IDENTITY" not in selected else "persisted ExplanationContract provenance"})
    out.append({"component":"repeatability","state":"APPLICABLE" if "REPLAY_INTEGRITY" in selected else "NOT_APPLICABLE","reason":"deterministic product replay"})
    out.append({"component":"numerical_completeness","state":"APPLICABLE" if "NATIVE_NUMERICAL" in selected and explainer!="occlusion" else "NOT_APPLICABLE","reason":"descriptive only; WARN is not a detector" if explainer!="occlusion" else "occlusion has no additivity claim"})
    for metric in ("faithfulness_correlation","max_sensitivity"):
        state=quantus_state if "EXTERNAL_QUANTUS" in selected else "NOT_APPLICABLE"
        out.append({"component":metric,"state":state,"reason":"synthetic compatibility preflight" if state=="AVAILABLE" else "external Quantus excluded from mode or unavailable"})
    if family=="L1_LOW_FIDELITY" and explainer=="occlusion":
        for row in out: row["state"]="NOT_APPLICABLE"; row["reason"]="L1 unavailable for exact occlusion route"
    return out

def main() -> dict:
    matrix=json.loads((CONFIG/"matrix_phase0_2.json").read_text()); corrupt=json.loads((CONFIG/"corruption_spec_phase0_1.json").read_text())
    preflight=json.loads((CONFIG/"quantus_synthetic_preflight.json").read_text()) if (CONFIG/"quantus_synthetic_preflight.json").exists() else {"state":"NOT_AVAILABLE"}
    quantus_state="AVAILABLE" if preflight.get("state")=="AVAILABLE" else "NOT_AVAILABLE"
    artifacts=[]; evaluations=[]; app=[]; oracle={}
    for family, detail in corrupt["families"].items():
        for subtype in detail["subtypes"]: oracle[f"{family}/{subtype}"]={"expected_component":expected_component(family,subtype),"acceptable_native_reason_names":[expected_component(family,subtype)],"generic_failed_is_localized":False}
    for dataset in matrix["datasets"]:
      for model, explainers in matrix["models"].items():
       for explainer in explainers:
        for slot in range(matrix["samples_per_dataset_model"]):
          clean_key=key("clean",dataset,model,explainer,slot)
          clean={"artifact_key":clean_key,"clean_artifact_key":clean_key,"pair_id":key("clean-pair",dataset,model,explainer,slot),"artifact_role":"CLEAN","dataset_id":dataset,"model_family":model,"explainer":explainer,"sample_slot":slot,"failure_family":"CLEAN","failure_subtype":"clean","severity":"NONE","effective_severity_parameters":{"severity":"NONE"},"expected_applicability":"APPLICABLE","expected_localization_component":None,"artifact_execution":"fresh_product_native_clean_explanation","benchmark_execution_forbidden":True}
          artifacts.append(clean)
          conditions=[clean]
          for family,detail in corrupt["families"].items():
           for subtype in detail["subtypes"]:
            for severity in severity_values(detail):
             state,reason=l1_state(explainer) if family=="L1_LOW_FIDELITY" else ("APPLICABLE","Declared contract/explainer route.")
             conditions.append({"artifact_key":key("corrupt",dataset,model,explainer,slot,family,subtype,severity),"clean_artifact_key":clean_key,"pair_id":key("pair",dataset,model,explainer,slot,family,subtype,severity),"artifact_role":"CORRUPT","dataset_id":dataset,"model_family":model,"explainer":explainer,"sample_slot":slot,"failure_family":family,"failure_subtype":subtype,"severity":severity,"effective_severity_parameters":effective(family,subtype,severity),"expected_applicability":state,"applicability_reason":reason,"expected_localization_component":expected_component(family,subtype),"artifact_execution":"fresh_product_native_reduced_budget_explanation" if family=="L1_LOW_FIDELITY" else "clean_contract_one_violation_mutation","benchmark_execution_forbidden":True})
          for artifact in conditions:
           if artifact["artifact_role"]=="CORRUPT": artifacts.append(artifact)
           for mode in matrix["validator_modes"]:
            row=dict(artifact); row["validator_mode"]=mode; row["execution_id"]=key("evaluation",artifact["artifact_key"],mode); row["component_applicability"]=components(explainer,artifact["failure_family"],artifact["failure_subtype"],mode,quantus_state); evaluations.append(row)
            for component in row["component_applicability"]: app.append({"dataset_id":dataset,"model_family":model,"explainer":explainer,"failure_family":artifact["failure_family"],"failure_subtype":artifact["failure_subtype"],"validator_mode":mode,**component})
    for filename,rows in (("locked_artifact_plan_phase0_2.jsonl",artifacts),("locked_execution_plan_phase0_2.jsonl",evaluations)):(CONFIG/filename).write_text("".join(canonical(r)+"\n" for r in rows))
    unique={canonical(r):r for r in app}; (CONFIG/"component_applicability_matrix.json").write_text(canonical({"schema_version":2,"rows":list(unique.values())})+"\n")
    (CONFIG/"localization_oracle_phase0_2.json").write_text(canonical({"schema_version":2,"oracle":oracle})+"\n")
    return {"clean_artifacts":sum(x["artifact_role"]=="CLEAN" for x in artifacts),"corrupt_artifacts":sum(x["artifact_role"]=="CORRUPT" for x in artifacts),"clean_evaluations":sum(x["artifact_role"]=="CLEAN" for x in evaluations),"corrupt_evaluations":sum(x["artifact_role"]=="CORRUPT" for x in evaluations),"evaluations":len(evaluations)}

if __name__=="__main__": print(canonical(main()))
