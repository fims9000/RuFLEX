import numpy as np
import pytest
from a06_streaming import (dataset_bundles,split_indices,freeze_threshold,
   stream_reject,batch_reject,score_arrays,metrics,uniform_ties)


def test_frozen_expected_review_and_ties():
    x=np.array([.8,.8,.8,.8,.2,.2,.2,.2,.1,.1])
    a=freeze_threshold(x,.8)
    assert a['expected_review']==2 and a['count_tied']==4
    assert a['tie_rejection_probability']==.5
    assert np.array_equal(stream_reject(x,np.arange(10),a,5),stream_reject(x,np.arange(10),a,5))


def test_holdout_scores_do_not_change_threshold():
    a=freeze_threshold(np.array([.1,.2,.3,.4,.5,.6,.7,.8,.9,1]),.8)
    b=np.array([20,22,29,3,7],dtype=float)
    a0=a.copy()
    stream_reject(b,np.arange(10,15),a,1)
    assert a==a0


def test_single_case_stream_same_as_batch_application():
    x=np.array([.1,.2,.2,.9,.2,.15])
    ids=np.array([8,3,2,0,13,1])
    a=freeze_threshold(x,.8)
    whole=stream_reject(x,ids,a,1)
    alone=np.array([stream_reject(x[i:i+1],ids[i:i+1],a,1)[0] for i in range(len(x))])
    assert np.array_equal(whole,alone)


def test_batch_matched_and_label_blind():
    s=np.array([1.,.5,.5,.1,.1,.2,.5,0.])
    a=batch_reject(s,np.arange(8),.75,11)
    assert a.sum()==2
    assert np.array_equal(a,batch_reject(s,np.arange(8),.75,11))


def test_scores_finite_with_saturated_probabilities():
    p=np.array([0,1,0.5]);ref=np.array([0,1,1]);audit=np.array([[0,0],[1,1],[0,1]],dtype=float)
    s,agree,std=score_arrays(p,ref,audit,audit.astype(int))
    assert np.isfinite(np.array([s[k] for k in s])).all()
    assert np.allclose(agree,[1,1,.5])


def test_modechoice_group_leakage_guard():
    d=next(x for x in dataset_bundles() if x[0].startswith('modechoice'))
    _,X,y,g=d
    tr,val,te=split_indices(y,g,303)
    assert not set(g[tr])&set(g[val]) and not set(g[tr])&set(g[te]) and not set(g[val])&set(g[te])


def test_stream_masks_depend_on_scores_not_labels():
    s=np.array([.4,.7,.8,.1,.3,.1,.2,.9,.5,.6]);ids=np.arange(10)
    a=freeze_threshold(s,.8);r=stream_reject(s,ids,a,4)
    y=np.zeros(10);y[0]=1
    assert np.array_equal(r,stream_reject(s,ids,a,4))
    assert metrics(y,np.zeros(10),r)['coverage']==(10-r.sum())/10


def test_invalid_stream_scores():
    a=freeze_threshold(np.arange(10),.8)
    with pytest.raises(ValueError):stream_reject(np.ones(2),np.arange(3),a,1)
