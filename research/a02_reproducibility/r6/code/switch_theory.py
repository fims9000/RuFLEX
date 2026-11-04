"""R6: exact policy-switch accounting and conditional-shift robustness.

The observed gain identity is deterministic for fixed labels and policies.
The risk-transport inequality is valid only under the stated bound on
conditional error-probability shift and common observable support.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import numpy as np


def _aligned(error, base, augmented):
    e=np.asarray(error,dtype=float)
    b=np.asarray(base,dtype=bool)
    a=np.asarray(augmented,dtype=bool)
    if e.ndim!=1 or not len(e) or e.shape!=a.shape or e.shape!=b.shape:
        raise ValueError('nonempty aligned one-dimensional case arrays required')
    if not np.isfinite(e).all() or not np.isin(e,[0,1]).all():
        raise ValueError('error indicator must be binary and finite')
    return e,b,a


@dataclass(frozen=True)
class SwitchSummary:
    n: int
    base_reviews: int
    augmented_reviews: int
    extra_reviewed: int
    released_from_review: int
    extra_review_errors: int
    released_errors: int
    switch_fraction: float
    gain: float
    exact_cost_gain: float
    fragility_epsilon: float | None


def paired_switch_summary(error, base, augmented, lam:float=.25)->SwitchSummary:
    """Positive gain means augmented policy has LOWER joint review+error cost.

    gain=E[(a-b)*(e-lam)] where a,b are review indicators.  It equals
    (errors newly reviewed - errors newly released - lam*(#a-#b))/n.
    This is an *accounting identity*, not a sampling-based guarantee.
    """
    if not np.isfinite(lam) or not 0<=lam<=1:
        raise ValueError('lambda must lie in [0,1]')
    e,b,a=_aligned(error,base,augmented)
    extra=a&~b;released=b&~a
    m=int(np.count_nonzero(extra|released));n=len(e)
    extra_err=int(np.sum(e[extra]));released_err=int(np.sum(e[released]))
    gain=(extra_err-released_err-lam*(np.sum(a)-np.sum(b)))/n
    direct=np.mean(e*(1-b)+lam*b)-np.mean(e*(1-a)+lam*a)
    if not np.isclose(gain,direct,atol=1e-12):
        raise AssertionError('switch accounting mismatch')
    return SwitchSummary(n=n,base_reviews=int(b.sum()),augmented_reviews=int(a.sum()),
       extra_reviewed=int(extra.sum()),released_from_review=int(released.sum()),
       extra_review_errors=extra_err,released_errors=released_err,
       switch_fraction=m/n,gain=float(gain),exact_cost_gain=float(direct),
       fragility_epsilon=(float(max(0,gain)/(m/n)) if m else None))


def transported_gain_bounds(source_risk, augmented, base, lam:float,
                            max_conditional_risk_shift:float,
                            source_risk_model_error:float=0)->tuple[float,float,float]:
    """Target-side observable policy masks and source conditional-error risks.

    If each |r_Q(z)-r_P(z)|<=eps and |r_P(z)-rhat_P(z)|<=eta uniformly,
    with z consisting of exactly the observed routing features, then
       |G_Q - E_Q[(a-b)*(rhat_P(z)-lam)]| <= (eps+eta)*P_Q(a!=b).
    No bound on r_Q-r_P follows from unlabeled covariates alone.
    """
    r=np.asarray(source_risk,dtype=float)
    b=np.asarray(base,dtype=bool);a=np.asarray(augmented,dtype=bool)
    if r.ndim!=1 or len(r)==0 or r.shape!=a.shape or r.shape!=b.shape:
        raise ValueError('aligned source risk and masks required')
    if not np.isfinite(r).all() or not ((0<=r)&(r<=1)).all():
        raise ValueError('risks are probabilities')
    if any(not np.isfinite(v) or v<0 or v>1 for v in (lam,max_conditional_risk_shift,source_risk_model_error)):
        raise ValueError('lambda and shift/error bounds must lie in [0,1]')
    pred=float(np.mean((a.astype(int)-b.astype(int))*(r-lam)))
    radius=float(np.mean(a!=b)*(max_conditional_risk_shift+source_risk_model_error))
    return pred-radius,pred+radius,pred


def sign_flip_worlds():
    """Two populations with identical observable Z and opposing optimal review policy.

    Each Z has probability 1/2. The reference classifier always predicts 0.
    The conditional label error is either (0.1,0.7) or (0.7,0.1).
    Since label risk can be changed while P(Z) is fixed, unlabelled
    predictions and disagreement cannot identify correctness or review gain.
    """
    p_z=np.array([.5,.5]);base=np.array([1,0]);aug=np.array([0,1]);lam=.25
    worlds=[]
    for name,r in [('A',np.array([.1,.7])),('B',np.array([.7,.1]))]:
        worlds.append({'world':name,'observable_probabilities':p_z.tolist(),
          'reference_predictions':[0,0],'disagreement':[0.,1.],
          'conditional_error_risks':r.tolist(),
          'expected_gain':float(np.sum(p_z*(aug-base)*(r-lam)))})
    return worlds


def _cp_interval(k:int,n:int,level:float)->tuple[float,float]:
    """Exact Clopper-Pearson two-sided interval for a binomial probability."""
    from scipy.stats import beta
    if not isinstance(k,int) or not isinstance(n,int) or not 0<=k<=n or n<0:
        raise ValueError('invalid binomial counts')
    if not 0<level<1:raise ValueError('level must be in (0,1)')
    if n==0:return 0.,1.
    tail=(1-level)/2
    lo=float(beta.ppf(tail,k,n-k+1)) if k else 0.
    hi=float(beta.ppf(1-tail,k+1,n-k)) if k<n else 1.
    return lo,hi


def switch_set_certificate(error,base,augmented,lam:float=.25,alpha:float=.05)->dict:
    """A conservative one-sided (1-alpha) lower bound for population gain.

    Four two-sided Clopper-Pearson intervals, each with failure probability
    alpha/4, cover P(S+),P(S-),P(E=1|S+),P(E=1|S-) simultaneously by the
    union bound.  Policies MUST have been frozen without using any of the
    certification cases (including their observable features for fitting or
    threshold selection).  Calibration cases must be IID from the SAME
    evaluation law for a population-valid statement; temporally dependent
    windows do not satisfy this assumption by default.

    If a switch set is empty, P(E=1|S) is unidentified; use [0,1].
    """
    if not 0<alpha<1 or not 0<=lam<=1:raise ValueError('invalid alpha or lambda')
    e,b,a=_aligned(error,base,augmented)
    n=len(e);plus=a&~b;minus=b&~a
    kp=int(np.sum(e[plus]));km=int(np.sum(e[minus]));np_=int(plus.sum());nm=int(minus.sum())
    level=1-alpha/4
    qp=_cp_interval(np_,n,level);qm=_cp_interval(nm,n,level)
    rp=_cp_interval(kp,np_,level);rm=_cp_interval(km,nm,level)
    low_pos=min(q*(r-lam) for q in qp for r in rp)
    up_neg=max(q*(r-lam) for q in qm for r in rm)
    lower=float(low_pos-up_neg)
    empirical=float((kp-km-lam*(np_-nm))/n)
    return {'n':n,'review_only_augmented':np_,'review_only_baseline':nm,
      'errors_only_augmented':kp,'errors_only_baseline':km,
      'empirical_gain':empirical,'lower_gain_confidence':lower,
      'certified_positive':bool(lower>0), 'alpha':alpha,
      'intervals':{'q_plus':qp,'q_minus':qm,'r_plus':rp,'r_minus':rm},
      'scope':'IID independent certification cases, fixed policies; no distribution shift guarantee'}
