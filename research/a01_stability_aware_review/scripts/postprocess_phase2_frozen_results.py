"""POST_EXECUTION_READ_ONLY A01 reporting, figures, and result freeze builder."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from research.a01_stability_aware_review.post_execution import RESULTS, canonical, independent_audit, load_json, recompute_cell, sha256

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"

def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(canonical(value) + "\n", encoding="utf-8")

def _label(cell: dict[str, Any]) -> str: return f"{cell['dataset_id'].replace('uci_', '').replace('_diagnostic','')}\n{cell['model_family'].replace('_',' ')}"

def figures(root: Path, audit: dict[str, Any]) -> list[Path]:
    frozen = load_json(root / "A01_FINAL_RESULTS.json"); cells = frozen["cells"]; d = root / "figures"; d.mkdir(exist_ok=True)
    # F05: three frozen policies only; no curve or threshold sweep.
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    for ax, dataset in zip(axes, ("ai4i_2020", "uci_bank_marketing", "wisconsin_diagnostic")):
        group = [c for c in cells if c["dataset_id"] == dataset]; x = list(range(len(group)))
        for name, key, color in (("No review", "no_review", "#6c757d"), ("Confidence-only frozen", "confidence_only_frozen", "#3366cc"), ("Stability Gate frozen", "stability_gate_frozen", "#d62728")):
            ax.scatter([c[key]["coverage"] for c in group], [c[key]["accepted_risk"] for c in group], label=name, color=color, s=55)
        for i,c in enumerate(group): ax.annotate(c["model_family"].replace("_", " "), (c["stability_gate_frozen"]["coverage"],c["stability_gate_frozen"]["accepted_risk"]), fontsize=7)
        ax.set_title(dataset); ax.set_ylabel("accepted-case risk"); ax.grid(alpha=.2)
    axes[-1].set_xlabel("coverage (three pre-frozen policies; no operating-point sweep)"); axes[0].legend(ncol=3, fontsize=8)
    fig.tight_layout(); p=d / "F05_final_test_frozen_policy_outcomes.png"; fig.savefig(p, dpi=160, metadata={"Creator":"RuFLEX POST_EXECUTION_READ_ONLY"}); plt.close(fig)
    # F06: forest-like H3 result.
    ordered = [c for dataset in ("ai4i_2020","uci_bank_marketing","wisconsin_diagnostic") for c in cells if c["dataset_id"] == dataset]
    fig, ax = plt.subplots(figsize=(11, 8)); y=list(range(len(ordered)))
    for i,c in enumerate(ordered):
        ci=c["bootstrap"]["delta_risk"]["percentile_ci_95"]; value=c["observed_delta_risk"]; color={"SUPPORTS_H3":"#2a9d8f","CONTRADICTS_H3":"#e76f51"}.get(c["h3_status"],"#6c757d")
        ax.errorbar(value, i, xerr=[[value-ci[0]],[ci[1]-value]], fmt="o", color=color, capsize=3)
    ax.axvline(0, color="black", linewidth=1); ax.set_yticks(y,[_label(c) for c in ordered]); ax.invert_yaxis(); ax.set_xlabel("Delta accepted-case risk (Stability − confidence), 95% percentile CI"); ax.grid(axis="x", alpha=.25)
    fig.tight_layout(); p2=d / "F06_delta_accepted_case_risk.png"; fig.savefig(p2,dpi=160,metadata={"Creator":"RuFLEX POST_EXECUTION_READ_ONLY"});plt.close(fig)
    # F07: only AI4I FNRs with actual denominators.
    ai=[c for c in cells if c["dataset_id"] == "ai4i_2020"]; fig,ax=plt.subplots(figsize=(12,5)); width=.25; policies=[("no_review","No review"),("confidence_only_frozen","Confidence"),("stability_gate_frozen","Stability")]
    for j,(key,name) in enumerate(policies):
        values=[c["ai4i_fnr"][key]["accepted_case_fnr"] for c in ai]; ax.bar([i+(j-1)*width for i in range(len(ai))], values, width, label=name)
        for i,c in enumerate(ai): ax.annotate(f"n={c['ai4i_fnr'][key]['accepted_positive_count']}",(i+(j-1)*width,values[i]),ha="center",va="bottom",fontsize=7)
    ax.set_xticks(range(len(ai)),[c["model_family"].replace("_"," ") for c in ai]); ax.set_ylabel("accepted-case FNR");ax.set_title("AI4I accepted-case FNR (n = accepted true positives)");ax.legend();ax.grid(axis="y",alpha=.2)
    fig.tight_layout();p3=d/"F07_ai4i_accepted_case_fnr.png";fig.savefig(p3,dpi=160,metadata={"Creator":"RuFLEX POST_EXECUTION_READ_ONLY"});plt.close(fig)
    # F08: actual final-test unstable cases only.
    unstable=[]
    by_id={(r["dataset_id"],r["model_family"]):r for r in audit["recomputed_cells"]}
    for cell in cells:
        for row in by_id[(cell["dataset_id"],cell["model_family"])]["unstable_cases"]:
            unstable.append((cell,row))
    unstable.sort(key=lambda item:(item[1]["selected_run_agreement"],-item[1]["confidence"],item[1]["case_id"]))
    fig,ax=plt.subplots(figsize=(12,5))
    if not unstable:
        ax.text(.5,.5,"NO FINAL-TEST CASES MET THE FROZEN INSTABILITY DEFINITION",ha="center",va="center",wrap=True);ax.set_axis_off()
    else:
        chosen=unstable[:10]; ax.scatter(range(len(chosen)),[r["selected_run_agreement"] for _,r in chosen],s=70,c="#d62728")
        ax.axhline(.8,color="black",linestyle="--"); ax.set_ylim(0,.85);ax.set_ylabel("selected-run agreement");ax.set_xticks(range(len(chosen)),[f"{c['dataset_id']}\n{c['model_family']}\n{r['case_id']}" for c,r in chosen],rotation=35,ha="right",fontsize=7);ax.set_title("Deterministically selected real final-test unstable cases")
    fig.tight_layout();p4=d/"F08_real_frozen_unstable_cases.png";fig.savefig(p4,dpi=160,metadata={"Creator":"RuFLEX POST_EXECUTION_READ_ONLY"});plt.close(fig)
    return [p,p2,p3,p4]

def report(root: Path, audit: dict[str, Any]) -> Path:
    result=load_json(root/"A01_FINAL_RESULTS.json"); cells=result["cells"]
    h3={key:sum(c["h3_status"]==key for c in cells) for key in ("SUPPORTS_H3","CONTRADICTS_H3","INCONCLUSIVE","NOT_ASSESSABLE")}
    h2=load_json(ROOT/"results/phase1_5_audit/PHASE1_5_AUDIT_RECEIPT.json")["h2_counts"]
    rows=[]
    for c in cells:
        ci=c["bootstrap"]["delta_risk"]["percentile_ci_95"]
        rows.append(f"| {c['dataset_id']} | {c['model_family']} | {c['no_review']['accepted_risk']:.6f} | {c['confidence_only_frozen']['accepted_risk']:.6f} | {c['stability_gate_frozen']['accepted_risk']:.6f} | {c['observed_delta_risk']:.6f} | [{ci[0]:.6f}, {ci[1]:.6f}] | {c['h3_status']} |")
    text=f"""# A01 final confirmatory results

## 1. Research question

Does a validation-frozen Stability Gate change accepted-case risk relative to a validation-matched frozen confidence-only policy? This report is a **POST_EXECUTION_READ_ONLY** presentation of the immutable final result.

## 2. Frozen protocol

Three datasets × five model families were evaluated using 300 pre-frozen fitted runs, validation-derived raw thresholds and policies, and one logical 15-cell final-test batch. No policy, threshold, selected run, preprocessing transform, or model was changed after opening.

## 3. Pre-final-test history

Phase 0 locked the executable protocol; Phase 0.5 locked the statistical analysis plan; Phase 1 froze validation evidence and policies; Phase 1.5 audited the H1 defect and retained H2; Phase 1.75 froze the executor and dry route. H1 remains `NOT_ASSESSABLE` because `PRE_SPECIFIED_COMPACTNESS_RULE_UNDERSPECIFIED`.

## 4. One-time final-test opening

Unlock SHA-256: `{sha256(root/'A01_FINAL_TEST_UNLOCK.json')}`
Opening receipt SHA-256: `{sha256(root/'FINAL_TEST_OPENING_RECEIPT.json')}`

## 5. H2 frozen validation interpretation

The Phase 1.5 independent validation audit retained {h2['PATTERN_OBSERVED']} `PATTERN_OBSERVED` and {h2['PATTERN_NOT_OBSERVED']} `PATTERN_NOT_OBSERVED` cells. H2 is not redefined from final-test data.

## 6. Final policy outcomes and H3

| Dataset | Model | No-review risk | Confidence risk | Stability risk | Delta_R | 95% CI | H3 |
|---|---|---:|---:|---:|---:|---|---|
{chr(10).join(rows)}

Global H3 counts: `SUPPORTS_H3={h3['SUPPORTS_H3']}`, `CONTRADICTS_H3={h3['CONTRADICTS_H3']}`, `INCONCLUSIVE={h3['INCONCLUSIVE']}`, `NOT_ASSESSABLE={h3['NOT_ASSESSABLE']}`.

## 7. AI4I FNR

AI4I FNR values and accepted-positive denominators are in immutable `T07_ai4i_fnr.csv` and F07. N/A values, if any, are not represented as zero.

## 8. Negative and inconclusive findings

The result is heterogeneous: AI4I Decision Tree supports H3; the other four primary AI4I families are inconclusive. Bank Marketing Decision Tree contradicts H3; all remaining secondary cells are inconclusive. Flat Neuro-Fuzzy remains included as frozen negative validation evidence; its Phase 1.5 audit found probability/class semantics and frozen threshold replay valid despite F1=0 at the standard 0.5 operating point on AI4I and Bank.

## 9. Independent recomputation

Status: `{audit['status']}`. It recomputed policy dispositions, risks, FNR where applicable, all paired 10,000-replicate bootstrap quantities (seed 20260902), and H3 labels from persisted product final-test case evidence rather than result summaries.

## 10. Allowed claim

In this pre-specified confirmatory experiment, stability-aware selective review was not universally advantageous. On primary AI4I, a statistically supported reduction in accepted-case risk was observed for Decision Tree, while the other four frozen model families were inconclusive. For Bank Marketing Decision Tree the effect was in the opposite direction; the remaining secondary cells were predominantly inconclusive. Cross-run stability therefore behaved as a regime-dependent review signal, not a universal substitute for confidence-based abstention.

## 11. Forbidden claims

This study does not establish universal risk reduction, universal H3 confirmation, superiority of RuFLEX over confidence-only review, or domain validation for industrial, financial, or clinical deployment.
"""
    out=root/"A01_FINAL_RESULTS.md";out.write_text(text,encoding="utf-8");return out

def manifest(root: Path, audit_path: Path, report_path: Path, figure_paths: list[Path]) -> Path:
    phase0=load_json(CONFIG/"locked_manifest.json"); p05=load_json(CONFIG/"phase0_5_manifest.json"); p15=load_json(CONFIG/"phase1_5_scientific_freeze_manifest.json");p175=load_json(CONFIG/"phase1_75_executor_freeze_manifest.json");p1=load_json(ROOT/"results/phase1_validation/phase1_validation_freeze_manifest.json")
    tables={p.name:sha256(p) for p in sorted((root/"tables").glob("T*.csv"))}; figs={p.name:sha256(p) for p in figure_paths}
    payload={"schema_version":1,"role":"POST_EXECUTION_READ_ONLY","phase0_manifest_id":phase0.get("manifest_id"),"phase0_5_manifest_id":p05.get("manifest_id"),"phase1_manifest_id":p1.get("manifest_id"),"phase1_5_manifest_id":p15.get("manifest_id"),"phase1_75_manifest_id":p175.get("manifest_id"),"unlock_sha256":sha256(root/"A01_FINAL_TEST_UNLOCK.json"),"opening_receipt_sha256":sha256(root/"FINAL_TEST_OPENING_RECEIPT.json"),"confirmatory_execution_code_sha":p175["executor_bindings"]["phase2_executor_sha256"],"statistics_sha256":p175["executor_bindings"]["statistics_sha256"],"result_schema_sha256":p175["executor_bindings"]["result_schema_sha256"],"post_execution_reporting_code_sha":sha256(Path(__file__)),"final_test_ids":sorted(c["final_test_id"] for c in load_json(root/"A01_FINAL_RESULTS.json")["cells"]),"immutable_result_json_sha256":sha256(root/"A01_FINAL_RESULTS.json"),"tables":tables,"figures":figs,"report_sha256":sha256(report_path),"independent_recomputation_sha256":sha256(audit_path)}
    payload["manifest_id"]=hashlib.sha256(canonical(payload).encode()).hexdigest();out=root/"A01_FINAL_RESULT_FREEZE_MANIFEST.json";write(out,payload);return out

def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("--result-root",type=Path,default=RESULTS);p.add_argument("--use-existing-audit",action="store_true");a=p.parse_args();root=a.result_root
    audit_path=root/"A01_PHASE2_INDEPENDENT_RECOMPUTATION.json"
    audit=load_json(audit_path) if a.use_existing_audit else independent_audit(root,output=audit_path)
    if audit["status"] != "INDEPENDENT_RECOMPUTATION_PASS":raise SystemExit("independent audit failed; immutable primary result retained")
    figs=figures(root,audit);rep=report(root,audit);man=manifest(root,audit_path,rep,figs)
    receipt={"schema_version":1,"role":"POST_EXECUTION_READ_ONLY","status":"FROZEN_COMPLETE","final_result_manifest_id":load_json(man)["manifest_id"],"opening_receipt_sha256":sha256(root/"FINAL_TEST_OPENING_RECEIPT.json"),"immutable_result_json_sha256":sha256(root/"A01_FINAL_RESULTS.json"),"independent_audit":"PASS","freeze_timestamp":datetime.now(timezone.utc).isoformat()}
    write(root/"A01_FINAL_RESULT_FREEZE_RECEIPT.json",receipt);print(f"POST_EXECUTION_FREEZE_COMPLETE {load_json(man)['manifest_id']}")

if __name__=="__main__":main()
