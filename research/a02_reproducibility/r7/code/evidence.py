"""R7: paired policy gains and always-valid e-processes for bounded conditional means.

No claim of validity unless each fed observation obeys the stated conditional
mean null. In particular, multiple countries in the same year do not form
conditionally unbiased sequential observations under a shared year shock.
"""
from __future__ import annotations
import hashlib
import math
import numpy as np

STAKES = (0.03, 0.07, 0.15, 0.30, 0.60)


def stable_unit(key: str, seed: int) -> float:
    z = hashlib.sha256(f"{seed}|{key}".encode()).digest()
    return int.from_bytes(z[:8], 'big') / 2**64


def choose_threshold(scores, keys, fraction: float, seed: int):
    """Pick a frozen validation score threshold and an exact tie-probability.

    Batch validation counts are exact to floor(fraction*n); target predictions
    are individually routed by the frozen score threshold and hashed tie rule.
    """
    s=np.asarray(scores, dtype=float)
    if s.ndim != 1 or len(s) == 0 or not np.isfinite(s).all():
        raise ValueError('finite one-dimensional scores required')
    if len(keys)!=len(s) or not 0 < fraction < 1:
        raise ValueError('invalid keys or budget')
    n=len(s); k=int(np.floor(fraction*n))
    if not 0 < k < n:raise ValueError('nontrivial review count required')
    idx=np.lexsort((np.array([stable_unit(str(z),seed) for z in keys]),-s))
    v=float(s[idx[k-1]])
    n_above=int(np.sum(s>v)); n_equal=int(np.sum(s==v))
    tie=(k-n_above)/n_equal
    return {'score_cutoff':v,'tie_probability':float(tie),
            'validation_n':int(n),'validation_review_target':k}


def review_masks(scores, keys, rule: dict, seed:int):
    s=np.asarray(scores,dtype=float)
    if s.ndim!=1 or len(keys)!=len(s) or not np.isfinite(s).all():
        raise ValueError('invalid scores/keys')
    t=rule['score_cutoff'];p=rule['tie_probability']
    if not np.isfinite(t) or not 0<=p<=1:raise ValueError('invalid rule')
    return (s>t)|((s==t)&(np.array([stable_unit(str(k),seed) for k in keys])<p))


def policy_gain(errors, base, augmented, review_cost=.25):
    e=np.asarray(errors,dtype=float)
    b=np.asarray(base,dtype=bool)
    a=np.asarray(augmented,dtype=bool)
    if e.ndim!=1 or not len(e) or e.shape!=b.shape or e.shape!=a.shape:
        raise ValueError('aligned 1D arrays needed')
    if not np.all(np.isin(e,[0.,1.])) or not 0 <= review_cost <= 1:
        raise ValueError('invalid error indicator or cost')
    return (a.astype(float)-b.astype(float))*(e-review_cost)


def method_cost(errors, reviews, review_cost=.25):
    return float(np.mean(np.asarray(errors)*(1-np.asarray(reviews,dtype=int)) +
                         review_cost*np.asarray(reviews,dtype=int)))


def mixture_path(gains, stakes=STAKES, side='benefit'):
    """K_t = mean_eta product_i (1+eta * s * gain_i).

    Under H0: E[s*gain_t | F_{t-1}] <= 0, and predictable routing,
    each factor is a nonnegative supermartingale increment. The mixture
    obeys Ville's anytime inequality even with serial dependence when
    the *conditional mean null itself* holds at each step.
    """
    x=np.asarray(gains,dtype=float)
    st=np.asarray(stakes,dtype=float)
    if x.ndim!=1 or not np.isfinite(x).all() or np.any(np.abs(x)>1+1e-12):
        raise ValueError('bounded finite 1D gain observations required')
    if st.ndim!=1 or not len(st) or np.any(st<=0) or np.any(st>=1):
        raise ValueError('stakes must lie strictly between 0 and 1')
    if side not in ('benefit','harm'):raise ValueError('invalid side')
    sign=1 if side=='benefit' else -1
    logw=np.zeros(len(st));out=[]
    for z in x:
        logw+=np.log1p(st*sign*z)
        maxlog=float(np.max(logw))
        evalue=math.exp(maxlog)*float(np.exp(logw-maxlog).mean())
        out.append(evalue)
    return np.array(out, dtype=float)


def first_evidence_time(path, alpha=.05):
    if not 0<alpha<1:raise ValueError('alpha in (0,1)')
    a=np.flatnonzero(np.asarray(path)>=1/alpha)
    return int(a[0]+1) if len(a) else None


def simulate_correlated_years(replicates=1000, years=12, countries=200, seed=71301):
    """Independently zero-mean *years*, perfectly correlated within each year.

    Analysing country rows as if they were successive iid observations is
    INVALID; this demonstrates its anti-conservative false alarm tendency.
    """
    rng=np.random.default_rng(seed)
    records=[]
    for i in range(replicates):
        shocks=0.5*rng.choice([-1,1],size=years)
        naive=mixture_path(np.repeat(shocks,countries))
        grouped=mixture_path(shocks)
        records.append({'rep':i, 'naive':bool((naive>=20).any()),
                        'year_aggregated':bool((grouped>=20).any()),
                        'maximum_e_naive':float(np.max(naive)),
                        'maximum_e_grouped':float(np.max(grouped))})
    return records
