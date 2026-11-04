import numpy as np
import pytest
from switch_theory import paired_switch_summary,transported_gain_bounds,sign_flip_worlds

def test_exact_switch_identity_general():
    rng=np.random.default_rng(20261104)
    for n in [3,7,100,2000]:
        e=rng.integers(0,2,n)
        for _ in range(10):
            b=rng.integers(0,2,n).astype(bool)
            a=rng.integers(0,2,n).astype(bool)
            lam=float(rng.uniform())
            s=paired_switch_summary(e,b,a,lam)
            assert np.isclose(s.gain,s.exact_cost_gain,atol=1e-12)
            assert s.extra_reviewed+s.released_from_review==int((a!=b).sum())

def test_same_masks_zero_gain():
    a=np.array([True,False,True]);s=paired_switch_summary([0,1,1],a,a)
    assert s.gain==0 and s.switch_fraction==0 and s.fragility_epsilon is None

def test_exact_matched_budget_cancels_lambda():
    e=np.array([0,1,1,0]);a=[1,0,1,0];b=[0,1,0,1]
    values=[paired_switch_summary(e,b,a,lam).gain for lam in (0.,.25,.5,1.)]
    assert len(set(values))==1

def test_transport_robustness_sharp_unclipped():
    r=np.array([.35,.65]);a=np.array([1,0],bool);b=np.array([0,1],bool)
    eps=.1;low,hi,pred=transported_gain_bounds(r,a,b,.25,eps)
    assert np.isclose(pred,.15) or np.isclose(pred,-.15)
    # maximize/minimize by shifting true risk in opposite directions on switch sets
    diff=a.astype(float)-b.astype(float)
    q1=r+eps*np.sign(diff)
    q2=r-eps*np.sign(diff)
    g1=np.mean(diff*(q1-.25));g2=np.mean(diff*(q2-.25))
    assert np.isclose(max(g1,g2),hi) and np.isclose(min(g1,g2),low)

def test_label_nonidentification():
    w=sign_flip_worlds();assert w[0]['observable_probabilities']==w[1]['observable_probabilities']
    assert w[0]['disagreement']==w[1]['disagreement']
    assert w[0]['expected_gain']>0 and w[1]['expected_gain']<0

def test_invalid_arguments():
    with pytest.raises(ValueError):paired_switch_summary([1,0],[True],[False])
    with pytest.raises(ValueError):paired_switch_summary([.6,0],[True,False],[False,True])
    with pytest.raises(ValueError):transported_gain_bounds([1.2], [True],[False],.2,.1)

from switch_theory import switch_set_certificate

def test_certification_requires_independent_evidence():
    c=switch_set_certificate([0,1,1,0],[1,0,0,1],[0,1,1,0],.25)
    assert c['empirical_gain']>0
    assert not c['certified_positive'] # too little data for a serious claim

def test_certificate_empty_switch():
    a=[1,0,1,0]
    c=switch_set_certificate([0,1,1,0],a,a)
    assert not c['certified_positive']
    assert c['empirical_gain']==0

def test_certificate_strong_ideal_signal():
    n=5000
    # Fixed selectors differ on balanced subgroups; all extra reviews find
    # errors while releases are correct (a simple constructed extreme).
    e=np.tile([1,0],n//2)
    b=np.tile([0,1],n//2).astype(bool)
    a=~b
    c=switch_set_certificate(e,b,a,.25)
    assert c['certified_positive']
    assert c['lower_gain_confidence']<=c['empirical_gain']

def test_certification_bounds_monte_carlo_null():
    rng=np.random.default_rng(42)
    # Fixed policies, independent certification observations, zero TRUE gain:
    # each switch group has error probability lambda, so no policy is better.
    false_cert=0
    for _ in range(100):
        n=400
        z=rng.integers(0,2,n)
        a=z.astype(bool);b=~a;e=(rng.uniform(size=n)<.25).astype(int)
        false_cert+=switch_set_certificate(e,b,a,.25)['certified_positive']
    assert false_cert<=3, false_cert

def test_hidden_shift_sharpness_and_unlabeled_impossibility():
    from simulate_switch_worlds import world,oracle_gain,decisions
    source,target,_=world('invisible_reversal')
    assert not np.array_equal(source,target)
    # 4 equally probable observable feature cells, of which just one switches.
    group=np.array([0,0,1,1]);d=np.array([0,1,0,1]);b,a=decisions('invisible_reversal',group,d)
    diff=a.astype(int)-b.astype(int);q=.25*np.ones(4)
    switch_fraction=float(np.dot(q,abs(diff)))
    epsilon=float(np.max(abs(source-target)))
    src=oracle_gain('invisible_reversal',source)
    tgt=oracle_gain('invisible_reversal',target)
    assert np.isclose(src,.05)
    assert np.isclose(tgt,-.125)
    assert np.isclose(src-tgt,epsilon*switch_fraction)
    lo,hi,pred=transported_gain_bounds(source[group,d],a,b,.25,epsilon)
    assert np.isclose(lo,tgt) # globally sharp for this construction
