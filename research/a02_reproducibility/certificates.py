"""A02: finite-sample evidence for frozen-reference prediction reproducibility.

This module does not train or select models.  A caller fixes the reference
model and the target threshold before observing the *independent* audit fits.
Calibration predictions from fits used to select that reference are invalid.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable


def _binomial_upper_tail(k: int, n: int, p: float) -> float:
    if k == 0:
        return 1.0
    return sum(math.comb(n, j) * p**j * (1.0 - p)**(n - j) for j in range(k, n + 1))


@lru_cache(maxsize=4096)
def exact_one_sided_lower(k: int, n: int, alpha: float = 0.05) -> float:
    """Clopper-Pearson lower limit for n IID Bernoulli trials, confidence 1-alpha.

    Defined by Pr_{p_lower}(Bin(n,p_lower)>=k)=alpha (k>0).
    Guaranteed coverage is conditional on a fixed target event and IID trials.
    """
    if not (isinstance(k, int) and isinstance(n, int) and 0 <= k <= n <= 512):
        raise ValueError("require integer 0 <= successes <= trials <= 512")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must lie strictly between 0 and 1")
    if k == 0:
        return 0.0
    if k == n:
        return alpha ** (1.0 / n)
    low, high = 0.0, 1.0
    for _ in range(70):
        mid = (low + high) / 2.0
        if _binomial_upper_tail(k, n, mid) >= alpha:
            high = mid
        else:
            low = mid
    return (low + high) / 2.0


def min_perfect_runs(target: float, alpha: float = 0.05) -> int:
    """Smallest number of all-agreeing independent fits needed for p_lower>=target."""
    if not (0 < target < 1 and 0 < alpha < 1):
        raise ValueError("target and alpha must lie strictly between 0 and 1")
    n = max(1, math.ceil(math.log(alpha) / math.log(target)))
    while alpha ** (1 / n) < target:
        n += 1
    return n


def multiclass_margin_certificate(scores: Iterable[float], epsilon: float) -> bool:
    """Sufficient argmax certificate if ALL fresh runs satisfy sup-norm <=epsilon.

    Observed maximum drift across 20 fits is NOT an upper bound on unseen fits.
    Strict > handles ties conservatively.
    """
    values = list(scores)
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError("need at least two finite class scores")
    if not (math.isfinite(epsilon) and epsilon >= 0):
        raise ValueError("epsilon must be finite and nonnegative")
    largest = sorted(values, reverse=True)
    return (largest[0] - largest[1]) > 2 * epsilon


def binary_threshold_certificate(probability: float, threshold: float, epsilon: float) -> bool:
    """Sufficient label invariance if fresh-run |p_new-p_ref|<=epsilon.

    Uses actual decision threshold, which A01 tuned on validation (not always .5).
    """
    if not (0 <= probability <= 1 and 0 < threshold < 1 and epsilon >= 0 and
            math.isfinite(probability) and math.isfinite(threshold) and math.isfinite(epsilon)):
        raise ValueError("invalid probability, threshold, or perturbation bound")
    return abs(probability - threshold) > epsilon


def audit_reference(
    references: dict[str, str],
    calibration: dict[str, dict[int, str]],
    *, declared_seeds: list[int], alpha: float = 0.05,
    target: float = 0.90, correction: str = "bonferroni",
    reference_seed: int | None = None,
) -> list[dict[str, object]]:
    """Make case-level certificates from a fixed reference and fresh IID runs.

    All declared seeds must be present exactly once for each case.  The caller
    must ensure seed draws represent independent randomized training runs, not
    run-selection leftovers. Bonferroni provides simultaneous coverage across
    the reference case set without assuming cases are independent.
    """
    if not references:
        raise ValueError("at least one reference case is required")
    if not (0 < alpha < 1 and 0.5 <= target < 1):
        raise ValueError("alpha in (0,1), target in [0.5,1) required")
    if correction not in {"none", "bonferroni"}:
        raise ValueError("correction must be 'none' or 'bonferroni'")
    if not declared_seeds or len(declared_seeds) != len(set(declared_seeds)):
        raise ValueError("declared seeds must be nonempty and unique")
    if reference_seed is not None and reference_seed in declared_seeds:
        raise ValueError("reference seed cannot be reused for independent calibration")
    if set(calibration) != set(references):
        raise ValueError("reference and calibration case identities differ")
    expected = set(declared_seeds)
    limit = alpha / len(references) if correction == "bonferroni" else alpha
    out = []
    for case_id in sorted(references):
        seed_labels = calibration[case_id]
        if set(seed_labels) != expected:
            raise ValueError(f"missing or extra calibration seeds in case {case_id!r}")
        hits = sum(seed_labels[s] == references[case_id] for s in declared_seeds)
        lower = exact_one_sided_lower(hits, len(declared_seeds), limit)
        out.append({
            "case_id": case_id, "reference_class": references[case_id],
            "n_independent_runs": len(declared_seeds), "agreements": hits,
            "observed_agreement": hits / len(declared_seeds),
            "one_sided_lower_bound": lower, "target_probability": target,
            "confidence_level": 1 - alpha, "alpha_per_case": limit,
            "multiplicity_correction": correction,
            "certified": lower >= target,
        })
    return out


def read_reference_csv(path: Path) -> tuple[dict[str, str], int | None]:
    out = {}
    seed_values = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not {"case_id", "reference_class"}.issubset(reader.fieldnames or []):
            raise ValueError("reference CSV requires case_id,reference_class columns")
        for row in reader:
            key = row["case_id"].strip()
            if not key or key in out or not row["reference_class"].strip():
                raise ValueError("empty/duplicate reference case or label")
            out[key] = row["reference_class"].strip()
            if row.get("reference_seed", "").strip():
                seed_values.add(int(row["reference_seed"]))
    if len(seed_values) > 1:
        raise ValueError("all reference rows must use the same frozen reference_seed")
    return out, next(iter(seed_values)) if seed_values else None


def read_calibration_csv(path: Path) -> dict[str, dict[int, str]]:
    out = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not {"case_id", "seed", "prediction"}.issubset(reader.fieldnames or []):
            raise ValueError("calibration CSV requires case_id,seed,prediction columns")
        for row in reader:
            key, label = row["case_id"].strip(), row["prediction"].strip()
            seed = int(row["seed"])
            if not key or not label or seed in out[key]:
                raise ValueError("empty or duplicate calibration case/seed/prediction")
            out[key][seed] = label
    return dict(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--seeds", required=True, help="fresh declared seed range: start:end exclusive")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target", type=float, default=0.90)
    parser.add_argument("--correction", choices=["bonferroni", "none"], default="bonferroni")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    a, b = map(int, args.seeds.split(":"))
    if not (0 <= a < b <= 2**32):
        parser.error("expected an increasing fresh seed range")
    references, reference_seed = read_reference_csv(args.reference)
    rows = audit_reference(references, read_calibration_csv(args.calibration),
                           declared_seeds=list(range(a, b)), reference_seed=reference_seed,
                           alpha=args.alpha, target=args.target, correction=args.correction)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "role": "A02_EXPLORATORY_FRESH_RUN_AUDIT",
        "case_count": len(rows), "certified_count": sum(row["certified"] for row in rows),
        "rows": rows}, indent=2) + "\n", encoding="utf-8")
    print(f"A02: {sum(row['certified'] for row in rows)}/{len(rows)} cases certified")


if __name__ == "__main__":
    main()
