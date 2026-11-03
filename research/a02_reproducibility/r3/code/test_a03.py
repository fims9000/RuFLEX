import json
from pathlib import Path
import numpy as np
import pytest
from a03_heldout import review_mask, bootstrap_delta, scores, split, tie_hash, assess


def test_exact_budget_and_stability():
    x=np.array([.9,.3,.3,.1,.2,.5,.4,.7,.6,.8])
    ids=np.arange(10)
    a=review_mask(x,ids,.8,tie_seed=0)
    assert a.sum()==2
    assert np.array_equal(a,review_mask(x,ids,.8,tie_seed=0))
    assert a[0] and a[9]


def test_selection_does_not_need_labels():
    scores_=np.array([.1,.4,.5,.5,.9,.1])
    ids=np.arange(len(scores_))
    a=review_mask(scores_,ids,.5)
    assert a.sum()==3
    assert np.array_equal(a,review_mask(scores_,ids,.5))


def test_selected_error_accounting():
    y=np.array([0,1,1,0]);yp=np.array([0,0,1,1])
    reject=np.array([0,1,0,0],dtype=bool)
    r=assess(y,yp,reject)
    assert r['accepted_errors']==1 and r['reviewed_errors']==1
    assert r['accepted_risk']==pytest.approx(1/3)


def test_train_val_test_separation():
    x=np.random.default_rng(42).normal(size=(200,5));y=np.repeat([0,1],100)
    *_,vi,ti,tr=split(x,y,101)
    assert not set(vi)&set(ti)
    assert not set(tr)&set(vi)
    assert not set(tr)&set(ti)


def test_uncertainty_formula_and_error_ci():
    z=scores(np.array([.8]),np.array([.5]),np.array([.1]))
    assert z['combined_fixed'][0]==pytest.approx(.45)
    y=np.array([0,1]*20);yp=np.array([0,0]*20)
    rej=np.zeros(40,dtype=bool)
    ci=bootstrap_delta(y,yp,rej,rej,seed=0,reps=100)
    assert ci['delta_ci95']==[0.0,0.0]


def test_invalid_input():
    with pytest.raises(ValueError): review_mask(np.ones(4),np.arange(4),1.0)
