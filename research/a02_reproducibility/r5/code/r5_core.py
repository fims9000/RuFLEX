"""R5: frozen reference, conditional error-risk and operational review utility.

All risk models are fitted on validation labels only.  No label from the
held-out chronological block is used in scoring, ranking or threshold fitting.
The value-of-information identity applies only to *true* conditional risks;
it does not guarantee improvement by either fitted model in this file.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class FrozenThreshold:
    cutoff: float
    tie_probability: float
    requested_count: int
    n_calibration: int


def deterministic_uniform(key: object, seed: int) -> float:
    digest = hashlib.sha256(f"R5|{seed}|{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def frozen_threshold(scores: Iterable[float], review_fraction: float) -> FrozenThreshold:
    z = np.asarray(list(scores), dtype=float)
    if z.ndim != 1 or len(z) < 3 or not np.isfinite(z).all():
        raise ValueError("need at least three finite validation scores")
    if not 0 < review_fraction < 1:
        raise ValueError("review fraction must be in (0,1)")
    k = int(math.ceil(review_fraction * len(z) - 1e-12))
    cutoff = float(np.partition(z, len(z)-k)[len(z)-k])
    above = int(np.count_nonzero(z > cutoff))
    equal = int(np.count_nonzero(z == cutoff))
    prob = (k-above)/equal
    if not 0 <= prob <= 1:
        raise AssertionError("invalid frozen tie rate")
    return FrozenThreshold(cutoff, prob, k, len(z))


def frozen_stream_review(scores, identities, threshold: FrozenThreshold, seed: int):
    z = np.asarray(scores, dtype=float)
    ids = list(identities)
    if len(z) != len(ids) or not np.isfinite(z).all():
        raise ValueError("case-score mismatch or nonfinite score")
    tie = np.asarray([deterministic_uniform(k, seed) for k in ids])
    return (z > threshold.cutoff) | ((z == threshold.cutoff) & (tie < threshold.tie_probability))


def batch_exact_review(scores, identities, review_fraction: float, seed: int):
    z = np.asarray(scores, dtype=float)
    ids = list(identities)
    if len(z) != len(ids) or not np.isfinite(z).all():
        raise ValueError("case-score mismatch or nonfinite score")
    k = int(math.ceil(review_fraction*len(z)-1e-12))
    t = np.asarray([deterministic_uniform(x, seed) for x in ids])
    order = np.lexsort((t, -z))
    mask = np.zeros(len(z), dtype=bool)
    mask[order[:k]] = True
    return mask


def risk_features(confidence, prediction, disagreement, dispersion, augmented: bool):
    c = np.asarray(confidence, dtype=float)
    p = np.asarray(prediction, dtype=float)
    d = np.asarray(disagreement, dtype=float)
    s = np.asarray(dispersion, dtype=float)
    if not (c.shape == p.shape == d.shape == s.shape) or c.ndim != 1:
        raise ValueError("all risk features must be one-dimensional and aligned")
    if not (np.isfinite(c).all() and np.isfinite(p).all() and np.isfinite(d).all() and np.isfinite(s).all()):
        raise ValueError("non-finite risk feature")
    if not ((c >= 0.5).all() and (c <= 1).all() and (d >= 0).all() and (d <= 1).all() and (s >= 0).all()):
        raise ValueError("risk feature outside valid range")
    uncertainty = 1.0-c
    features = [uncertainty, p]
    if augmented:
        features.extend([d, s, uncertainty*d])
    return np.column_stack(features)


def train_error_model(features, observed_error):
    x = np.asarray(features, dtype=float)
    y = np.asarray(observed_error, dtype=int)
    if x.ndim != 2 or len(x) != len(y) or len(x) < 4 or not set(np.unique(y)).issubset({0,1}):
        raise ValueError("invalid training data for error risk model")
    if len(np.unique(y)) == 1:
        # Do not fabricate a discriminative model when validation errors are all identical.
        model = DummyClassifier(strategy="constant", constant=int(y[0]))
    else:
        model = make_pipeline(StandardScaler(), LogisticRegression(
            C=1.0, solver="lbfgs", max_iter=1000, random_state=55042))
    return model.fit(x, y)


def predict_error_risk(model, features):
    classes = list(model.classes_ if hasattr(model,"classes_") else model[-1].classes_)
    proba = model.predict_proba(np.asarray(features, dtype=float))
    return np.asarray(proba[:, classes.index(1)] if 1 in classes else np.zeros(len(proba)), dtype=float)


def validate_policy_masks(truth, predicted, mask):
    y = np.asarray(truth, dtype=int)
    p = np.asarray(predicted, dtype=int)
    r = np.asarray(mask, dtype=bool)
    if y.ndim != 1 or len(y) == 0 or not (len(y) == len(p) == len(r)):
        raise ValueError("unaligned policy rows")
    if not set(np.unique(y)).issubset({0,1}) or not set(np.unique(p)).issubset({0,1}):
        raise ValueError("binary labels expected")
    return y != p, r


def policy_metrics(truth, predicted, review_mask, review_cost):
    if not 0 <= review_cost <= 1:
        raise ValueError("review cost must lie between zero and one")
    err, rev = validate_policy_masks(truth, predicted, review_mask)
    accepted = ~rev
    return {
        "n": int(len(err)),
        "reviewed": int(np.count_nonzero(rev)),
        "coverage": float(np.mean(accepted)),
        "accepted_errors": int(np.count_nonzero(err & accepted)),
        "accepted_risk": float(np.mean(err[accepted])) if np.any(accepted) else None,
        "captured_errors": int(np.count_nonzero(err & rev)),
        "total_reference_errors": int(np.count_nonzero(err)),
        "joint_review_cost": float(np.mean((err & accepted).astype(float)+review_cost*rev.astype(float))),
    }


def paired_moving_block_ci(differences, *, block_length: int, replicates: int=2000, seed: int=55044):
    """Paired descriptive bootstrap, preserving short-range temporal dependence.

    No formal population coverage guarantee is made under unknown nonstationarity.
    """
    z = np.asarray(differences, dtype=float)
    if z.ndim != 1 or len(z) < 4 or not np.isfinite(z).all() or not 1 <= block_length <= len(z):
        raise ValueError("invalid moving-block bootstrap data")
    rng = np.random.default_rng(seed)
    n = len(z)
    blocks = int(math.ceil(n / block_length))
    result = np.empty(replicates)
    for i in range(replicates):
        starts = rng.integers(0, n-block_length+1, size=blocks)
        samples = np.concatenate([z[start:start+block_length] for start in starts])[:n]
        result[i] = np.mean(samples)
    return [float(v) for v in np.quantile(result,[.025,.975])]


def extra_info_value(true_risk_with_extra, true_risk_base, review_cost):
    """Plug-in value expression; nonnegativity requires TRUE conditional risks.

    The guarantee relies on r_base = E[r_extra | base sigma-algebra].
    It is generally FALSE for arbitrary fitted probabilities.
    """
    r1 = np.asarray(true_risk_with_extra, dtype=float)
    r0 = np.asarray(true_risk_base, dtype=float)
    if r1.shape != r0.shape or not 0 <= review_cost <= 1:
        raise ValueError("risk shape/cost error")
    return float(np.mean(np.maximum(r1-review_cost, 0)-np.maximum(r0-review_cost,0)))
