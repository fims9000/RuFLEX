"""Fresh-seed A02 exploratory benchmark; never reruns or retunes A01 final test.

Uses only scikit-learn bundled public datasets and a separately declared
synthetic stress grid.  Three original A01 datasets and results remain frozen.
The operational model is fitted ONCE with a fixed reference seed, and all
fresh calibration fits use disjoint seeds.  The evaluation split is validation,
not a new confirmatory final test.  This run does not assert deployment safety.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import sklearn
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits, load_iris, load_wine, make_classification
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from certificates import audit_reference, min_perfect_runs


REFERENCE_SEED = 9_000
FRESH_SEED_START = 10_000
SPLIT_SEED = 42
MODEL_SPECS = ("logistic_regression", "decision_tree", "random_forest", "extra_trees", "sgd_log_loss")


def datasets(mode: str) -> list[tuple[str, np.ndarray, np.ndarray, str]]:
    found = []
    if mode in {"all", "bundled"}:
        for name, load, positive in (
            ("sklearn_iris_virginica", load_iris, 2),
            ("sklearn_wine_class0", load_wine, 0),
            ("sklearn_digits_5_to_9", load_digits, "half"),
        ):
            dataset = load()
            y = (dataset.target >= 5 if positive == "half" else dataset.target == positive).astype(int)
            found.append((name, np.asarray(dataset.data, dtype=float), y,
                          "public scikit-learn bundled dataset, binary mapping is A02 exploratory"))
    if mode in {"all", "stress"}:
        for sep, flip in ((1.5, 0.01), (0.5, 0.01), (1.5, 0.15), (0.5, 0.15)):
            x, y = make_classification(n_samples=1000, n_features=20, n_informative=5,
                n_redundant=3, n_repeated=0, n_classes=2, weights=[0.75, 0.25],
                class_sep=sep, flip_y=flip, random_state=20260923)
            found.append((f"synthetic_sep{sep}_noise{flip}", x, y,
                          "synthetic fixed-feature class-overlap/label-noise stress"))
    return found


def estimator(family: str, seed: int):
    if family == "logistic_regression":
        return LogisticRegression(max_iter=1000, solver="lbfgs", random_state=seed)
    if family == "decision_tree":
        return DecisionTreeClassifier(random_state=seed)
    if family == "random_forest":
        return RandomForestClassifier(n_estimators=25, max_features="sqrt", n_jobs=1,
                                      random_state=seed)
    if family == "extra_trees":
        return ExtraTreesClassifier(n_estimators=25, max_features="sqrt", n_jobs=1, random_state=seed)
    if family == "sgd_log_loss":
        return SGDClassifier(loss="log_loss", max_iter=1000, tol=1e-3, alpha=0.0001, random_state=seed)
    raise ValueError(family)


def split_and_normalize(x: np.ndarray, y: np.ndarray, *, split_seed: int = SPLIT_SEED):
    ids = np.arange(len(y))
    train, other = train_test_split(ids, train_size=0.6, random_state=split_seed, stratify=y)
    val, final = train_test_split(other, train_size=0.5, random_state=split_seed + 1,
                                  stratify=y[other])
    scaler = StandardScaler().fit(x[train])
    return scaler.transform(x[train]), y[train], scaler.transform(x[val]), y[val], train, val, final


def run_benchmark(out_dir: Path, *, mode: str = "all", n_seeds: int = 100,
                  target: float = 0.90, alpha: float = 0.05,
                  families: tuple[str, ...] = MODEL_SPECS, split_seed: int = SPLIT_SEED,
                  reference_seed: int = REFERENCE_SEED, fresh_seed_start: int = FRESH_SEED_START) -> dict:
    if n_seeds <= 0 or n_seeds > 512:
        raise ValueError("n_seeds must be in 1..512")
    if split_seed < 0 or reference_seed < 0 or fresh_seed_start < 0:
        raise ValueError("seed parameters must be nonnegative")
    if fresh_seed_start <= reference_seed < fresh_seed_start + n_seeds:
        raise ValueError("reference seed overlaps audit seeds")
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_results = []
    case_rows = []
    start = time.monotonic()
    seeds = list(range(fresh_seed_start, fresh_seed_start + n_seeds))
    for dataset_id, x, y, source_note in datasets(mode):
        train_x, train_y, val_x, val_y, train_ids, val_ids, final_ids = split_and_normalize(x, y, split_seed=split_seed)
        for family in families:
            cell_start = time.monotonic()
            fixed = estimator(family, reference_seed).fit(train_x, train_y)
            ref_y = fixed.predict(val_x).astype(int)
            ref_prob = fixed.predict_proba(val_x)
            ref_confidence = np.max(ref_prob, axis=1)
            references = {str(int(case_id)): str(int(label)) for case_id, label in zip(val_ids, ref_y)}
            calibration = {case_id: {} for case_id in references}
            for seed in seeds:
                replay = estimator(family, seed).fit(train_x, train_y)
                for case_id, label in zip(val_ids, replay.predict(val_x)):
                    calibration[str(int(case_id))][seed] = str(int(label))
            simultaneous = audit_reference(references, calibration,
                declared_seeds=seeds, alpha=alpha, target=target,
                correction="bonferroni", reference_seed=reference_seed)
            pointwise = audit_reference(references, calibration,
                declared_seeds=seeds, alpha=alpha, target=target,
                correction="none", reference_seed=reference_seed)
            px = {row["case_id"]: row for row in pointwise}
            sy = {row["case_id"]: row for row in simultaneous}
            high_conf = int(np.count_nonzero(ref_confidence >= .90))
            hcir = 0
            for pos, case_id in enumerate(val_ids):
                key = str(int(case_id))
                point = px[key]; simul = sy[key]
                if ref_confidence[pos] >= .90 and point["observed_agreement"] < .80:
                    hcir += 1
                case_rows.append({"dataset_id": dataset_id, "model_family": family,
                    "case_id": key, "reference_label": int(ref_y[pos]),
                    "truth": int(val_y[pos]), "confidence": float(ref_confidence[pos]),
                    "agreements": int(point["agreements"]),
                    "n_runs": n_seeds, "observed_agreement": point["observed_agreement"],
                    "pointwise_lower": point["one_sided_lower_bound"],
                    "simultaneous_lower": simul["one_sided_lower_bound"],
                    "pointwise_certified": point["certified"],
                    "simultaneous_certified": simul["certified"],
                    "reference_error": int(ref_y[pos] != val_y[pos])})
            cell_results.append({"dataset_id": dataset_id, "model_family": family,
                "data_source": source_note, "n_train": len(train_y), "n_validation": len(val_y),
                "n_untouched_final_test": len(final_ids), "n_calibration_fits": n_seeds,
                "reference_seed": reference_seed, "fresh_seed_range": [seeds[0], seeds[-1]],
                "train_indices_sha256": hashlib.sha256(np.sort(train_ids).astype("<i8").tobytes()).hexdigest(),
                "validation_indices_sha256": hashlib.sha256(np.sort(val_ids).astype("<i8").tobytes()).hexdigest(),
                "untouched_test_indices_sha256": hashlib.sha256(np.sort(final_ids).astype("<i8").tobytes()).hexdigest(),
                "reference_accuracy_validation": float(np.mean(ref_y == val_y)),
                "validation_hcir_count": hcir, "validation_high_confidence_count": high_conf,
                "validation_hcir": hcir / high_conf if high_conf else None,
                "pointwise_certified_count": sum(row["certified"] for row in pointwise),
                "simultaneously_certified_count": sum(row["certified"] for row in simultaneous),
                "elapsed_seconds": round(time.monotonic() - cell_start, 4)})
            print(f"{dataset_id:30s} {family:22s} cert {cell_results[-1]['simultaneously_certified_count']:3d}/{len(val_y):3d}; high-conf unstable {hcir:3d}/{high_conf:3d}", flush=True)
    with (out_dir / "case_level_validation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=case_rows[0].keys())
        writer.writeheader(); writer.writerows(case_rows)
    result = {"schema_version": 1, "study": "A02 independent-seed exploratory validation",
       "a01_unchanged": True, "train_fraction": 0.6, "validation_fraction": 0.2,
       "final_test_fraction": 0.2, "split_seed": split_seed,
       "scikit_learn_version": sklearn.__version__, "numpy_version": np.__version__,
       "final_test_used": False, "selection_rule": f"single fixed reference fit seed {reference_seed}, not picked from auxiliary runs",
       "confidence_rule": "max class probability of fixed reference, class decision argmax",
       "reference_reused_in_audit": False, "audit_assumption": "independent identically distributed training randomness for fresh seeds",
       "confidence_intervals": "one-sided exact Clopper-Pearson per case and Bonferroni simultaneous",
       "alpha": alpha, "target": target, "n_fresh_seeds": n_seeds,
       "reference_seed": reference_seed, "fresh_seed_start": fresh_seed_start,
       "minimum_all_agreeing_runs_pointwise": min_perfect_runs(target, alpha),
       "fit_count": len(cell_results) * (n_seeds + 1),
       "elapsed_seconds": round(time.monotonic() - start, 4),
       "cells": cell_results}
    (out_dir / "summary_validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["all", "bundled", "stress"], default="all")
    parser.add_argument("--n-seeds", type=int, default=100)
    parser.add_argument("--target", type=float, default=0.9)
    parser.add_argument("--families", type=str, default=",".join(MODEL_SPECS))
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--split-seed", type=int, default=SPLIT_SEED)
    parser.add_argument("--reference-seed", type=int, default=REFERENCE_SEED)
    parser.add_argument("--fresh-seed-start", type=int, default=FRESH_SEED_START)
    args = parser.parse_args()
    families = tuple(args.families.split(","))
    if not families or any(x not in MODEL_SPECS for x in families) or len(families) != len(set(families)):
        parser.error("--families must be distinct names from MODEL_SPECS")
    run_benchmark(args.output_dir, mode=args.mode, n_seeds=args.n_seeds,
                  target=args.target, alpha=args.alpha, families=families,
                  split_seed=args.split_seed, reference_seed=args.reference_seed,
                  fresh_seed_start=args.fresh_seed_start)