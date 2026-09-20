"""Post-hoc reduced-run approximation study for frozen A01 validation evidence.

The selected operational model is always retained. For run budget K, K-1
auxiliary frozen runs are sampled from the other 19 runs. No model is retrained,
no policy is refit, and no confirmatory artifact is modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

RUN_BUDGETS = (3, 5, 10, 15, 20)
MAX_SUBSETS = 1000
BASE_SEED = 20260920
MIN_CONFIDENCE = 0.90
MIN_AGREEMENT = 0.80
MAX_STD = 0.15


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed_for(dataset_id: str, model_family: str, k: int) -> int:
    raw = f"A01|PRACTICAL|{BASE_SEED}|{dataset_id}|{model_family}|{k}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**32)


def subset_plan(n: int, choose: int, seed: int):
    total = math.comb(n, choose)
    if total <= MAX_SUBSETS:
        return list(itertools.combinations(range(n), choose))
    rng = np.random.default_rng(seed)
    found = set()
    while len(found) < MAX_SUBSETS:
        found.add(tuple(sorted(int(v) for v in rng.choice(n, size=choose, replace=False))))
    return sorted(found)


def ratio(num: int, den: int):
    return None if den == 0 else num / den


def set_metrics(predicted: np.ndarray, reference: np.ndarray):
    tp = int(np.sum(predicted & reference))
    fp = int(np.sum(predicted & ~reference))
    fn = int(np.sum(~predicted & reference))
    union = int(np.sum(predicted | reference))
    return {
        "recall": ratio(tp, tp + fn),
        "precision": ratio(tp, tp + fp),
        "jaccard": ratio(tp, union),
    }


def summarize(values):
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if not len(arr):
        return {"median": None, "q25": None, "q75": None, "mean": None}
    return {
        "median": float(np.median(arr)),
        "q25": float(np.percentile(arr, 25)),
        "q75": float(np.percentile(arr, 75)),
        "mean": float(np.mean(arr)),
    }


def analyses(root: Path):
    rows = []
    for path in sorted((root / "projects").glob("*/*/analyses/stability-analyses/*.json")):
        if path.name == "active-analysis.json":
            continue
        analysis = load(path)
        if analysis.get("applicability") == "APPLICABLE" and analysis.get("validation_alignment_status") == "EXACT_MATCH":
            rows.append((path.parts[-5], path.parts[-4], path.parents[2], analysis))
    if len(rows) != 15:
        raise ValueError(f"Expected 15 applicable A01 cells, found {len(rows)}")
    return rows


def analyze_cell(dataset_id: str, model_family: str, project_root: Path, analysis: dict):
    cases = analysis["cases"]
    run_ids = [str(v) for v in analysis["run_ids"]]
    selected_id = str(analysis["selected_run_id"])
    selected_index = run_ids.index(selected_id)

    labels = np.asarray([[int(c["run_labels"][r]) for r in run_ids] for c in cases], dtype=np.int8)
    probs = np.asarray([[float(c["run_probabilities"][r]) for r in run_ids] for c in cases], dtype=float)
    selected_label = labels[:, selected_index]
    selected_prob = probs[:, selected_index]
    confidence = np.maximum(selected_prob, 1.0 - selected_prob)
    full_agreement = np.asarray([float(c["selected_run_agreement"]) for c in cases])
    full_std = np.asarray([float(c["std_probability"]) for c in cases])
    full_review = (confidence < MIN_CONFIDENCE) | (full_agreement < MIN_AGREEMENT) | (full_std > MAX_STD)
    full_hc_disagreement = (confidence >= MIN_CONFIDENCE) & (full_agreement < MIN_AGREEMENT)

    policy_paths = sorted((project_root / "analyses" / "stability-policies").glob("*.json"))
    if len(policy_paths) != 1:
        raise ValueError(f"Expected one frozen Stability Gate for {dataset_id}/{model_family}")
    policy = load(policy_paths[0])
    if (
        float(policy["min_confidence"]),
        float(policy["min_class_agreement"]),
        float(policy["max_probability_std"]),
    ) != (MIN_CONFIDENCE, MIN_AGREEMENT, MAX_STD):
        raise ValueError(f"Frozen thresholds differ for {dataset_id}/{model_family}")
    persisted_ids = [d["case_id"] for d in policy["decisions"]]
    persisted_review = np.asarray([d["disposition"] == "REVIEW" for d in policy["decisions"]], dtype=bool)
    if persisted_ids != [c["case_id"] for c in cases] or not np.array_equal(persisted_review, full_review):
        raise ValueError(f"Frozen gate replay failed for {dataset_id}/{model_family}")

    aux = [i for i in range(len(run_ids)) if i != selected_index]
    output = []
    detection = {i: {str(k): [] for k in RUN_BUDGETS if k < 20}
                 for i in range(len(cases)) if full_hc_disagreement[i]}

    for k in RUN_BUDGETS:
        subsets = [tuple(range(len(aux)))] if k == 20 else subset_plan(len(aux), k - 1, seed_for(dataset_id, model_family, k))
        metric = {name: [] for name in (
            "gate_decision_agreement", "review_recall", "review_precision", "review_jaccard",
            "hc_disagreement_recall", "hc_disagreement_precision", "hc_disagreement_jaccard",
            "agreement_mae", "review_workload", "review_workload_delta",
        )}
        for subset in subsets:
            idx = [selected_index, *[aux[j] for j in subset]]
            agreement = np.mean(labels[:, idx] == selected_label[:, None], axis=1)
            std = np.std(probs[:, idx], axis=1, ddof=0)
            review = (confidence < MIN_CONFIDENCE) | (agreement < MIN_AGREEMENT) | (std > MAX_STD)
            hc = (confidence >= MIN_CONFIDENCE) & (agreement < MIN_AGREEMENT)

            review_metrics = set_metrics(review, full_review)
            hc_metrics = set_metrics(hc, full_hc_disagreement)
            metric["gate_decision_agreement"].append(float(np.mean(review == full_review)))
            metric["review_recall"].append(review_metrics["recall"])
            metric["review_precision"].append(review_metrics["precision"])
            metric["review_jaccard"].append(review_metrics["jaccard"])
            metric["hc_disagreement_recall"].append(hc_metrics["recall"])
            metric["hc_disagreement_precision"].append(hc_metrics["precision"])
            metric["hc_disagreement_jaccard"].append(hc_metrics["jaccard"])
            metric["agreement_mae"].append(float(np.mean(np.abs(agreement - full_agreement))))
            workload = float(np.mean(review))
            metric["review_workload"].append(workload)
            metric["review_workload_delta"].append(workload - float(np.mean(full_review)))
            if k < 20:
                for case_index in detection:
                    detection[case_index][str(k)].append(float(hc[case_index]))

        row = {
            "dataset_id": dataset_id,
            "model_family": model_family,
            "k_total_runs": k,
            "auxiliary_runs": k - 1,
            "auxiliary_fit_fraction_of_full": (k - 1) / 19.0,
            "subset_count": len(subsets),
            "case_count": len(cases),
            "full_review_workload": float(np.mean(full_review)),
            "full_hc_disagreement_n": int(np.sum(full_hc_disagreement)),
        }
        for name, values in metric.items():
            for stat, value in summarize(values).items():
                row[f"{name}_{stat}"] = value
        output.append(row)

    case_rows = []
    for i, by_k in detection.items():
        case = cases[i]
        case_rows.append({
            "dataset_id": dataset_id,
            "model_family": model_family,
            "case_id": case["case_id"],
            "target": int(case["target"]),
            "selected_prediction": int(case["selected_run_class"]),
            "selected_confidence": float(confidence[i]),
            "full_selected_run_agreement": float(full_agreement[i]),
            "full_probability_std": float(full_std[i]),
            "selected_prediction_correct": bool(int(case["target"]) == int(case["selected_run_class"])),
            **{f"k{k}_hc_disagreement_detection_probability": float(np.mean(by_k[str(k)]))
               for k in RUN_BUDGETS if k < 20},
        })
    return output, case_rows


def macro_summary(cell_rows):
    fields = (
        "gate_decision_agreement_median", "review_recall_median", "review_precision_median",
        "review_jaccard_median", "hc_disagreement_recall_median",
        "hc_disagreement_precision_median", "hc_disagreement_jaccard_median",
        "agreement_mae_median", "review_workload_median", "review_workload_delta_median",
    )
    result = []
    for k in RUN_BUDGETS:
        rows = [r for r in cell_rows if r["k_total_runs"] == k]
        out = {
            "k_total_runs": k,
            "auxiliary_runs": k - 1,
            "auxiliary_fit_fraction_of_full": (k - 1) / 19.0,
            "cell_count": len(rows),
            "cells_with_full_hc_disagreement": sum(r["full_hc_disagreement_n"] > 0 for r in rows),
        }
        for field in fields:
            values = [r[field] for r in rows if r[field] is not None]
            out[field + "_macro"] = None if not values else float(np.mean(values))
            out[field + "_cell_median"] = None if not values else float(np.median(values))
        result.append(out)
    return result


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    cell_rows = []
    case_rows = []
    for dataset_id, model_family, project_root, analysis in analyses(args.validation_root):
        rows, cases = analyze_cell(dataset_id, model_family, project_root, analysis)
        cell_rows.extend(rows)
        case_rows.extend(cases)

    macro = macro_summary(cell_rows)
    bank = [r for r in case_rows if r["dataset_id"] == "uci_bank_marketing" and r["model_family"] == "decision_tree"]
    targets = [(False, 0.10), (False, 0.50), (False, 0.75), (True, 0.10), (True, 0.75)]
    chosen = []
    used = set()
    for correctness, target_agreement in targets:
        candidates = [r for r in bank if r["selected_prediction_correct"] is correctness and r["case_id"] not in used]
        row = min(candidates, key=lambda r: (
            abs(r["full_selected_run_agreement"] - target_agreement),
            -r["selected_confidence"], r["case_id"],
        ))
        chosen.append(row)
        used.add(row["case_id"])

    write_csv(args.output / "T13_reduced_run_practical_tradeoff.csv", cell_rows)
    write_csv(args.output / "T14_reduced_run_macro_summary.csv", macro)
    write_csv(args.output / "T15_bank_dt_illustrative_cases.csv", chosen)
    (args.output / "A01_PRACTICAL_REDUCED_RUN_RESULTS.json").write_text(
        json.dumps({
            "role": "POST_HOC_EXPLORATORY_PRACTICAL_ANALYSIS",
            "training_performed": False,
            "frozen_confirmatory_artifacts_modified": False,
            "run_budget_definition": "K total frozen runs = selected operational run + K-1 auxiliary runs",
            "thresholds": {"confidence": MIN_CONFIDENCE, "agreement": MIN_AGREEMENT, "probability_std": MAX_STD},
            "macro_summary": macro,
            "illustrative_bank_dt_cases": chosen,
        }, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
