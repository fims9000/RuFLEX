import numpy as np
import pytest
from r5_core import (
    frozen_threshold,frozen_stream_review,batch_exact_review,train_error_model,
    risk_features,predict_error_risk,policy_metrics,paired_moving_block_ci,
    extra_info_value,
)


def test_exact_review_and_labelblind_ties():
    z=[.5,.5,.5,.5,.4,.4,.1,.2,.9,.2]
    m=batch_exact_review(z,range(10),.2,55043)
    assert m.sum()==2
    assert m[8] == 1
    assert np.array_equal(m,batch_exact_review(z,range(10),.2,55043))


def test_frozen_threshold_independent_of_test_batch():
    a=frozen_threshold([.1,.4,.4,.4,.5,.6,.9,.8,.7,.2],.3)
    assert a.requested_count==3
    s=[.1,.5,.2,.9]
    first=frozen_stream_review(s,[100,200,300,400],a,55043)
    later=frozen_stream_review(s[2:],[300,400],a,55043)
    assert np.array_equal(first[2:],later)


def test_no_test_truth_required_for_risk_scoring():
    c=np.array([.5,.7,.8,.9,.99,.6,.6,.5])
    p=np.array([0,0,1,1,1,0,1,0])
    d=np.array([.4,.3,0,0,.1,.2,.1,0])
    a=risk_features(c,p,d,np.zeros(8),True)
    b=risk_features(c,p,d,np.zeros(8),False)
    assert a.shape==(8,5) and b.shape==(8,2)
    mdl=train_error_model(a,[0,1,0,1,0,0,1,0])
    out=predict_error_risk(mdl,a)
    assert out.shape==(8,) and np.all((out>=0)&(out<=1))


def test_single_class_validation_fails_closed():
    x=np.array([[1.,2.],[2.,2.],[3.,2.],[4.,2.]])
    a=train_error_model(x,[0,0,0,0])
    assert (predict_error_risk(a,x)==0).all()


def test_joint_cost_penalizes_review_and_autonomous_errors():
    e=policy_metrics([1,0,1,0],[0,0,1,1],[True,False,False,True],.25)
    assert e['joint_review_cost']==.125
    assert e['reviewed']==2 and e['captured_errors']==2 and e['accepted_errors']==0


def test_moving_block_ci_reproducible():
    d=np.arange(100,dtype=float)/100
    a=paired_moving_block_ci(d,block_length=10,replicates=300,seed=7)
    assert a==paired_moving_block_ci(d,block_length=10,replicates=300,seed=7)
    assert a[0] < a[1]


def test_value_of_information_for_exact_discrete_risk():
    # Constant baseline risk 0.4; auxiliary r1 takes values 0.1 and 0.7.
    # At lambda=0.4, extra information has positive value .15.
    r1=np.array([.1,.7]);r0=np.array([.4,.4])
    assert np.isclose(extra_info_value(r1,r0,.4),.15)
    # If both conditional risks are below the price of review, value is zero.
    assert extra_info_value([.1,.3],[.2,.2],.4)==0


def test_invalid_scores_rejected():
    with pytest.raises(ValueError):
        frozen_threshold([.1,float('nan'),.2],.2)
    with pytest.raises(ValueError):
        risk_features([.2],[0],[0],[0],True)
