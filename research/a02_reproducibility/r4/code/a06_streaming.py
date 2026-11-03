"""A06: external-domain fixed-reference audit with validation-frozen online thresholds.

Run only with the protocol frozen before viewing held-out labels.  All output
is exploratory; it does not replace A01, A02 or A03 findings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


POLICIES = ("confidence_only", "combined_fixed", "dispersion_fixed",
            "disagreement_only", "vote_uncertainty", "ensemble_entropy")


def dataset_bundles() -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray | None]]:
    """Embedded third-party data, not downloaded and not previously used by R3."""
    fair = sm.datasets.fair.load_pandas().data.copy()
    r = sm.datasets.randhie.load_pandas().data.copy()
    mode = sm.datasets.modechoice.load_pandas().data.copy()
    anes = sm.datasets.anes96.load_pandas().data.copy()
    specs = [
        ("fair_affair_any", fair, "affairs", (fair["affairs"] > 0).astype(int), None),
        ("randhie_doctor_visit_any", r, "mdvis", (r["mdvis"] > 0).astype(int), None),
        ("modechoice_alternative_selected", mode, "choice", (mode["choice"] == 1).astype(int), mode["individual"].to_numpy(dtype=int)),
        ("anes96_reported_vote", anes, "vote", (anes["vote"] == 1).astype(int), None),
    ]
    out = []
    for name, raw, target, y, groups in specs:
        excluded = {target, "individual", "PID"}  # PID omitted in ANES96
        columns = [col for col in raw.columns if col not in excluded]
        X = raw[columns].to_numpy(dtype=np.float64)
        y = y.to_numpy(dtype=np.int64)
        if X.ndim != 2 or X.shape[1] < 2 or len(set(y)) != 2 or not np.isfinite(X).all():
            raise ValueError("unexpected data shape, class distribution or missing value: " + name)
        if groups is not None:
            assert len(set(groups)) * 4 == len(groups), "modechoice choice sets unexpectedly changed"
        out.append((name, X, y, groups))
    return out


def dataset_digest(X, y, groups):
    h = hashlib.sha256()
    for array, dt in [(X, "<f8"), (y, "<i8")]:
        z = np.ascontiguousarray(array, dtype=dt)
        h.update(str(z.shape).encode("ascii")); h.update(z.tobytes())
    if groups is not None:
        z = np.ascontiguousarray(groups, dtype="<i8")
        h.update(z.tobytes())
    return h.hexdigest()


def split_indices(y, groups, seed):
    ids = np.arange(len(y), dtype=int)
    if groups is None:
        a, b = train_test_split(ids, train_size=.6, stratify=y, random_state=seed)
        v, t = train_test_split(b, train_size=.5, stratify=y[b], random_state=seed+1)
    else:
        # Entire choice sets stay in one partition.
        distinct = np.unique(groups)
        random = np.random.default_rng(seed)
        distinct = random.permutation(distinct)
        ntrain = round(.6 * len(distinct)); nval = round(.2 * len(distinct))
        a = ids[np.isin(groups, distinct[:ntrain])]
        v = ids[np.isin(groups, distinct[ntrain:ntrain+nval])]
        t = ids[np.isin(groups, distinct[ntrain+nval:])]
    if len(set(a)&set(v)) or len(set(a)&set(t)) or len(set(v)&set(t)):
        raise AssertionError("leakage across partitions")
    if groups is not None:
        assert not (set(groups[a]) & set(groups[v]))
        assert not (set(groups[a]) & set(groups[t]))
        assert not (set(groups[v]) & set(groups[t]))
    return a, v, t


def make_model(name, seed):
    if name == "logistic_regression":
        return LogisticRegression(max_iter=700, solver="lbfgs", random_state=seed)
    if name == "decision_tree":
        return DecisionTreeClassifier(random_state=seed, min_samples_leaf=2)
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=20, max_features="sqrt", min_samples_leaf=2, n_jobs=1, random_state=seed)
    if name == "sgd_log_loss":
        return SGDClassifier(loss="log_loss", alpha=.0001, max_iter=1000, tol=.001, random_state=seed)
    raise ValueError(name)


def score_arrays(p_ref, predicted_ref, audit_probs, audit_votes):
    n, m = audit_probs.shape
    if m < 2 or audit_votes.shape != audit_probs.shape:
        raise ValueError("unaligned audit predictions")
    conf = np.maximum(p_ref, 1-p_ref)
    agree = np.mean(audit_votes == predicted_ref[:,None], axis=1)
    std = audit_probs.std(axis=1)
    vote_p = np.mean(audit_votes, axis=1)
    mean_p = np.clip(audit_probs.mean(axis=1),1e-12,1-1e-12)
    entropy = -mean_p*np.log(mean_p)-(1-mean_p)*np.log(1-mean_p)
    return {
        "confidence_only": 1-conf,
        "combined_fixed": 1-conf + .5*(1-agree),
        "dispersion_fixed": 1-conf + .5*std,
        "disagreement_only": 1-agree,
        "vote_uncertainty": np.minimum(vote_p, 1-vote_p),
        "ensemble_entropy": entropy,
    }, agree, std


def uniform_ties(ids, seed):
    # Integer ids are independent of labels.  A seeded hash gives reproducible
    # pseudo-random tie resolution without dependence on the test batch size.
    vals=[]
    for x in ids:
        digest=hashlib.sha256(f"a06|{seed}|{int(x)}".encode("ascii")).digest()
        vals.append(int.from_bytes(digest[:8],"big") / (2**64))
    return np.asarray(vals)


def freeze_threshold(scores, target_coverage):
    """Use *validation only* to set cutoff and expected boundary rejection."""
    z=np.asarray(scores, dtype=float)
    if len(z)<5 or not np.all(np.isfinite(z)) or not (0<target_coverage<1):
        raise ValueError("invalid validation scores or target")
    k=math.ceil((1-target_coverage)*len(z)-1e-12)
    cut=float(np.sort(z)[::-1][k-1])
    above=int(np.sum(z>cut));ties=int(np.sum(z==cut))
    rate=(k-above)/ties
    if not 0<=rate<=1: raise AssertionError("bad tie rate")
    return {"threshold":cut,"tie_rejection_probability":float(rate),
            "n_validation":len(z),"expected_review":k,"count_above":above,"count_tied":ties}


def stream_reject(scores, ids, policy, seed):
    z=np.asarray(scores, dtype=float)
    if len(z)!=len(ids):raise ValueError("score/ids mismatch")
    t=policy["threshold"]
    return (z>t) | ((z==t) & (uniform_ties(ids, seed)<policy["tie_rejection_probability"]))


def batch_reject(scores, ids, target_coverage, seed):
    z=np.asarray(scores,dtype=float)
    k=math.ceil((1-target_coverage)*len(z)-1e-12)
    h=uniform_ties(ids,seed)
    order=np.lexsort((h,-z))
    reject=np.zeros(len(z),dtype=bool);reject[order[:k]]=True
    return reject


def metrics(y, prediction, review):
    incorrect=np.asarray(y)!=np.asarray(prediction)
    accepted=~review
    nacc=int(accepted.sum()); nrev=int(review.sum())
    return {"n":len(y), "reviewed":nrev, "coverage":float(nacc/len(y)),
            "accepted_errors":int((incorrect & accepted).sum()),
            "accepted_risk":float((incorrect&accepted).sum()/nacc) if nacc else None,
            "reviewed_errors":int((incorrect&review).sum()),
            "total_errors":int(incorrect.sum()),
            "reference_accuracy":float((~incorrect).mean())}


def write_rows(path, rows):
    if not rows:raise ValueError("empty output")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),extrasaction="ignore")
        w.writeheader();w.writerows(rows)


def run(protocol_path, output, only_dataset=None):
    raw=protocol_path.read_bytes();p=json.loads(raw)
    if p["version"]!=1 or p["reference_seed"] in range(*p["audit_seed_range"]):
        raise ValueError("bad protocol or seed leakage")
    output.mkdir(parents=True, exist_ok=True)
    manifest={"protocol_sha256":hashlib.sha256(raw).hexdigest(),"source":"statsmodels packaged datasets",
              "software":{"statsmodels":sm.__version__},"cells":[],"dataset_hashes":{},
              "status":"EXPLORATORY_VALIDATION_FROZEN"}
    (output/"START_RECEIPT.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    summary=[];cases=[];calibration=[];count=0
    for name,X,y,groups in dataset_bundles():
        if only_dataset and name!=only_dataset: continue
        manifest["dataset_hashes"][name]=dataset_digest(X,y,groups)
        for seed in p["split_seeds"]:
            train,val,test=split_indices(y,groups,seed)
            norm=StandardScaler().fit(X[train]); Xt=norm.transform(X[train]);Xv=norm.transform(X[val]);Xe=norm.transform(X[test])
            for family in p["models"]:
                cell=f"{name}::{family}::split{seed}"
                t0=time.monotonic()
                ref=make_model(family,p["reference_seed"]).fit(Xt,y[train]);count+=1
                refs=[ref.predict_proba(z)[:,1] for z in (Xv,Xe)]
                decisions=[ref.predict(z) for z in (Xv,Xe)]
                audit_p=[[],[]];audit_v=[[],[]]
                for audit_seed in range(*p["audit_seed_range"]):
                    clf=make_model(family,audit_seed).fit(Xt,y[train]);count+=1
                    for j,z in enumerate((Xv,Xe)):
                        audit_p[j].append(clf.predict_proba(z)[:,1]);audit_v[j].append(clf.predict(z))
                scored=[]
                for j in range(2):
                    ap=np.vstack(audit_p[j]).T;av=np.vstack(audit_v[j]).T
                    s,agr,sd=score_arrays(refs[j],decisions[j],ap,av)
                    scored.append((s,agr,sd))
                cal={policy:freeze_threshold(scored[0][0][policy],p["target_coverage"]) for policy in POLICIES}
                # One-by-one streaming decisions; test batch size unused in selection.
                for j,ids in enumerate((val,test)):
                    label="validation" if j==0 else "heldout"
                    s,agr,sd=scored[j]
                    for ii,rid in enumerate(ids):
                        cases.append({"cell":cell,"dataset":name,"split_seed":seed,"model":family,
                           "partition":label,"case_id":int(rid),"group_id":int(groups[rid]) if groups is not None else "",
                           "truth":int(y[rid]),"prediction":int(decisions[j][ii]),
                           "confidence":float(1-s["confidence_only"][ii]),
                           "agreement":float(agr[ii]),"std":float(sd[ii]),
                           **{f"score_{policy}":float(s[policy][ii]) for policy in POLICIES}})
                for policy in POLICIES:
                    cfg=cal[policy]
                    calibration.append({"cell":cell,"dataset":name,"model":family,
                        "split_seed":seed,"policy":policy,**cfg})
                    for tie_seed in p["tie_seeds"]:
                        reject=stream_reject(scored[1][0][policy],test,cfg,tie_seed)
                        mm=metrics(y[test],decisions[1],reject)
                        summary.append({"cell":cell,"dataset":name,"model":family,"split_seed":seed,
                          "policy":policy,"evaluation":"streaming_frozen","tie_seed":tie_seed,
                          "target_coverage":p["target_coverage"],"validation_expected_review":cfg["expected_review"],
                          **mm,"delta_coverage":mm["coverage"]-p["target_coverage"],
                          "cell_seconds":round(time.monotonic()-t0,3)})
                    review=batch_reject(scored[1][0][policy],test,p["target_coverage"],p["point_estimate_tie_seed"])
                    mm=metrics(y[test],decisions[1],review)
                    summary.append({"cell":cell,"dataset":name,"model":family,"split_seed":seed,
                       "policy":policy,"evaluation":"batch_exact_secondary","tie_seed":p["point_estimate_tie_seed"],
                       "target_coverage":p["target_coverage"],"validation_expected_review":cfg["expected_review"],
                       **mm,"delta_coverage":mm["coverage"]-p["target_coverage"],
                       "cell_seconds":round(time.monotonic()-t0,3)})
                manifest["cells"].append({"id":cell,"ntrain":len(train),"nval":len(val),"ntest":len(test),
                   "training_fits":1+p["audit_seed_range"][1]-p["audit_seed_range"][0],
                   "group_disjoint":bool(groups is None or not (set(groups[train])&set(groups[test]))),
                   "runtime_seconds":round(time.monotonic()-t0,2)})
                print(cell,"trainings",count,"secs",round(time.monotonic()-t0,2),flush=True)
                write_rows(output/"A06_SUMMARY_RUNNING.csv",summary)
    write_rows(output/"A06_SUMMARY.csv",summary)
    write_rows(output/"A06_CASE_LEVEL.csv",cases)
    write_rows(output/"A06_CALIBRATION.csv",calibration)
    manifest["total_fit_calls"]=count;manifest["n_cells"]=len(manifest["cells"])
    manifest["n_case_records"]=len(cases);manifest["n_policy_outcomes"]=len(summary)
    manifest["output_sha256"]={nm:hashlib.sha256((output/nm).read_bytes()).hexdigest() for nm in
              ("A06_SUMMARY.csv","A06_CASE_LEVEL.csv","A06_CALIBRATION.csv")}
    (output/"A06_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    pa=argparse.ArgumentParser();pa.add_argument("--protocol",type=Path,required=True)
    pa.add_argument("--out",type=Path,required=True)
    pa.add_argument("--dataset",default=None)
    a=pa.parse_args();print(json.dumps(run(a.protocol,a.out,a.dataset)["total_fit_calls"]))

if __name__ == "__main__":main()
