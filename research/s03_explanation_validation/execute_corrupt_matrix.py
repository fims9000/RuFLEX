"""Resumable R6 S03 corrupt-artifact and frozen validator-matrix executor."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pandas as pd

from research.s03_explanation_validation.corruptions.library import low_fidelity_generation_parameters, corrupt_contract, mutation_receipt
from research.s03_explanation_validation.execute_phase1_clean_baseline import A01_DATA, create_clean_explanation, sample_from_source
from research.s03_explanation_validation.execute_quantus_amendment import MODELS
from research.s03_explanation_validation.quantus_execution import METRICS, evaluate_metric
from ruflex.application.evidence import _persist_explanation, check_explanation, load_explanation
from ruflex.application.training import load_training_run

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
CLEAN = ROOT / "results" / "phase1_clean_baseline_r6"
AMENDMENT = ROOT / "results" / "quantus_amendment_r6"
OUT = ROOT / "results" / "phase2_corrupt_r6"


def canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
def sha_file(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path: Path) -> list[dict]: return [json.loads(line) for line in path.read_text().splitlines() if line]
def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(canonical(value)+"\n"); tmp.replace(path)
def atomic_jsonl(path: Path, value: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text("".join(canonical(x)+"\n" for x in value)); tmp.replace(path)


def _alternate(clean: dict, run_ledger: dict[tuple[str, str], dict]) -> UUID:
    return UUID(run_ledger[(clean["dataset_id"], MODELS[(MODELS.index(clean["model_family"])+1)%len(MODELS)])]["run_id"])


def _low_fidelity(root: Path, run, clean_contract, severity: str):
    params=low_fidelity_generation_parameters(clean_contract.generation_parameters, explainer={
        "train_reference_occlusion":"occlusion", "integrated_gradients_train_reference":"integrated_gradients",
        "gradient_shap_train_background":"gradient_shap", "permutation_shap_train_background":"permutation_shap", "tree_shap_train_background":"tree_shap",
    }[clean_contract.method], severity=severity)
    if params is None: raise RuntimeError("L1_NOT_APPLICABLE")
    sample=dict(clean_contract.sample)
    if clean_contract.method=="integrated_gradients_train_reference":
        from ruflex.application.evidence import create_integrated_gradients_explanation
        return create_integrated_gradients_explanation(root,run.run_id,sample,steps=int(params["steps"]))
    if clean_contract.method=="gradient_shap_train_background":
        from ruflex.application.evidence import create_gradient_shap_explanation
        return create_gradient_shap_explanation(root,run.run_id,sample,background_count=int(params["background_count"]))
    if clean_contract.method=="permutation_shap_train_background":
        from ruflex.application.evidence import create_permutation_shap_explanation
        return create_permutation_shap_explanation(root,run.run_id,sample,background_count=int(params["background_count"]),max_evals=int(params["max_evals"]))
    raise RuntimeError("L1_UNSUPPORTED_FROZEN_ROUTE")


def _component_map(check) -> dict[str, str]: return {item.name:item.status for item in check.checks}


def _metrics(clean_quantus: dict[tuple[str,str],dict], clean_key: str, root: Path, contract) -> dict[str,dict]:
    out={}
    for metric in METRICS:
        corrupt=evaluate_metric(root,contract,clean_artifact_key=clean_key,metric_name=metric)
        clean=clean_quantus[(clean_key,metric)]
        signalled=False
        if clean["state"]=="APPLICABLE" and corrupt.state=="APPLICABLE":
            if metric=="faithfulness_correlation": signalled=corrupt.value < float(clean["value"])-1e-12
            else: signalled=corrupt.value > float(clean["value"])+1e-12
        out[metric]={"clean_state":clean["state"],"clean_value":clean["value"],"corrupt_state":corrupt.state,"corrupt_value":corrupt.value,"signal":signalled,"effective_seed":corrupt.effective_seed,"target_run_id":corrupt.target_run_id,"reason":corrupt.reason}
    return out


def _evaluation(artifact: dict, mode: str, component: dict[str,str], metric: dict[str,dict], expected: str|None) -> dict:
    identity={"model_identity","preprocessing_identity","feature_order_identity","sample_target_identity","reference_identity"}
    identity_signal=any(component.get(name)=="FAIL" for name in identity)
    replay_signal=component.get("repeatability")=="FAIL"
    quantus_signal=any(value["signal"] for value in metric.values())
    if artifact["artifact_execution"]=="NOT_APPLICABLE_NO_ARTIFACT":
        state="NOT_APPLICABLE"; detected=None
    elif mode=="IDENTITY_ONLY": state="APPLICABLE"; detected=identity_signal
    elif mode=="METRIC_ONLY": state="APPLICABLE" if component.get("repeatability")!="N/A" or any(v["corrupt_state"]=="APPLICABLE" for v in metric.values()) else "NOT_APPLICABLE"; detected=(replay_signal or quantus_signal) if state=="APPLICABLE" else None
    else: state="APPLICABLE"; detected=identity_signal or replay_signal or quantus_signal
    localization=bool(expected and (component.get(expected)=="FAIL" or (expected=="external_quantus_or_replay_integrity" and (replay_signal or quantus_signal)))) if detected else False
    return {**artifact,"validator_mode":mode,"execution_id":hashlib.sha256(canonical({"artifact_key":artifact["artifact_key"],"mode":mode}).encode()).hexdigest()[:24],"evaluation_state":state,"detected":detected,"localized":localization,"check_components":component,"quantus":metric,"expected_localization_component":expected}


def main() -> dict:
    clean_manifest=json.loads((CLEAN/"PHASE1_CLEAN_FREEZE_MANIFEST.json").read_text())
    quantus_manifest=json.loads((AMENDMENT/"R6_CLEAN_QUANTUS_DETERMINISTIC_REFREEZE.json").read_text())
    if clean_manifest["corrupt_artifacts_executed"]!=0: raise RuntimeError("CLEAN_FREEZE_NOT_PRE_CORRUPT")
    clean={x["artifact_key"]:x for x in rows(CLEAN/"CLEAN_ARTIFACTS.jsonl")}
    plan=[x for x in rows(CONFIG/"locked_artifact_plan_phase0_2_treeshap_amendment.jsonl") if x["artifact_role"]=="CORRUPT"]
    if len(plan)!=5808: raise RuntimeError("CORRUPT_PLAN_COUNT")
    run_ledger={(x["dataset_id"],x["model_family"]):x for x in json.loads((CLEAN/"run_ledger.json").read_text())["rows"]}
    clean_quantus={(x["clean_artifact_key"],x["metric_name"]):x for x in rows(AMENDMENT/"CLEAN_QUANTUS_METRICS.jsonl")}
    artifacts_path=OUT/"CORRUPT_ARTIFACTS.jsonl"; eval_path=OUT/"CORRUPT_EVALUATIONS.jsonl"
    existing={x["artifact_key"]:x for x in rows(artifacts_path)} if artifacts_path.exists() else {}
    evaluations={x["execution_id"]:x for x in rows(eval_path)} if eval_path.exists() else {}
    for index, planned in enumerate(plan,1):
        stored=existing.get(planned["artifact_key"])
        if stored is None:
            parent=clean[planned["clean_artifact_key"]]; root=Path(parent["project_root"]); clean_contract=load_explanation(root,UUID(parent["explanation_id"]))
            started=time.perf_counter()
            if planned["artifact_execution"]=="NOT_APPLICABLE_NO_ARTIFACT":
                stored={**planned,"execution_state":"NOT_APPLICABLE","reason":"Frozen route has no meaningful low-fidelity knob.","created_at":datetime.now(timezone.utc).isoformat(),"runtime_seconds":time.perf_counter()-started}
                component={}; metric={}
            else:
                if planned["failure_family"]=="L1_LOW_FIDELITY": corrupt=_low_fidelity(root,load_training_run(root,clean_contract.run_id),clean_contract,planned["severity"]); changed=["generation_parameters"]
                else:
                    corrupt,changed=corrupt_contract(clean_contract,family=planned["failure_family"],subtype=planned["failure_subtype"],severity=planned["severity"],seed=3003,alternate_run_id=_alternate(parent,run_ledger))
                    corrupt=_persist_explanation(root,corrupt)
                check=check_explanation(root,corrupt.explanation_id); component=_component_map(check); metric=_metrics(clean_quantus,planned["clean_artifact_key"],root,corrupt)
                path=root/"evidence"/"explanations"/f"{corrupt.explanation_id}.json"
                stored={**planned,"execution_state":"PERSISTED_REOPENED_CHECKED","project_root":str(root),"clean_explanation_id":parent["explanation_id"],"clean_sha256":parent["explanation_sha256"],"explanation_id":str(corrupt.explanation_id),"explanation_sha256":sha_file(path),"check_id":str(check.check_id),"changed_fields":changed,"mutation_receipt":mutation_receipt(clean_contract,corrupt,family=planned["failure_family"],subtype=planned["failure_subtype"],severity=planned["severity"],seed=3003,changed_fields=changed) if planned["failure_family"]!="L1_LOW_FIDELITY" else {"fresh_product_native_reduced_budget":True,"changed_fields":changed},"check_components":component,"quantus":metric,"runtime_seconds":time.perf_counter()-started,"created_at":datetime.now(timezone.utc).isoformat()}
            existing[planned["artifact_key"]]=stored; atomic_jsonl(artifacts_path,[existing[k] for k in sorted(existing)])
        component=stored.get("check_components",{}); metric=stored.get("quantus",{})
        for mode in ("IDENTITY_ONLY","METRIC_ONLY","COMBINED"):
            eid=hashlib.sha256(canonical({"artifact_key":planned["artifact_key"],"mode":mode}).encode()).hexdigest()[:24]
            if eid not in evaluations:
                evaluations[eid]=_evaluation(stored,mode,component,metric,planned.get("expected_localization_component")); atomic_jsonl(eval_path,[evaluations[k] for k in sorted(evaluations)])
        if index % 10 == 0: print(canonical({"progress":index,"of":len(plan)}),flush=True)
    if len(existing)!=5808 or len(evaluations)!=17424: raise RuntimeError(f"ACCOUNTING:{len(existing)}/{len(evaluations)}")
    manifest={"schema_version":1,"study":"S03","status":"R6_CORRUPT_EXECUTION_COMPLETE","clean_manifest_id":clean_manifest["manifest_id"],"quantus_refreeze_id":quantus_manifest["refreeze_id"],"corrupt_artifacts":len(existing),"corrupt_evaluations":len(evaluations),"corrupt_artifacts_sha256":sha_file(artifacts_path),"corrupt_evaluations_sha256":sha_file(eval_path),"created_at":datetime.now(timezone.utc).isoformat()}; manifest["manifest_id"]=hashlib.sha256(canonical(manifest).encode()).hexdigest(); atomic_json(OUT/"CORRUPT_EXECUTION_MANIFEST.json",manifest); return manifest

if __name__=="__main__": print(canonical(main()))
