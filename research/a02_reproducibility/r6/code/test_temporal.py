import json
import numpy as np
import pytest
from run_new_temporal import (series_bundles,partitions,fit_threshold,
     apply_threshold,feature_matrix,train_risk_model,predict_err)

def test_independent_real_time_sources():
    data=series_bundles()
    assert len(data)==2
    assert data[0][1].shape[0]>290 and data[1][1].shape[0]>190
    for name,X,y,ids in data:
        assert len(X)==len(y)==len(ids) and not np.isnan(X).any()
        assert len(set(ids))==len(ids)
        assert set(np.unique(y))=={0,1}
        s=partitions(len(y))
        assert len(s)==5
        assert sum(map(len,s))+4==len(y)
        for a,b in zip(s[:-1],s[1:]):
            assert b[0]-a[-1]>=2
            assert not set(a)&set(b)

def test_frozen_threshold_reproducibility():
    v=np.array([.1,.3,.3,.6,.7,.8,.8,.8,.95,.95])
    t=fit_threshold(v,.30)
    assert t[0]==.8 and np.isclose(t[1],1/3)
    ids=[str(i) for i in range(len(v))]
    r=apply_threshold(v,ids,t)
    assert (r[v>.8]).all() and not (r[v<.8]).any()
    assert np.array_equal(r,apply_threshold(v,ids,t))
    # Expected 3 reviews under tie randomization, not guaranteed exactly 3.
    assert np.isclose(int((v>.8).sum())+int((v==.8).sum())*t[1],3.)

def test_feature_alignment_and_invalid():
    p=np.array([.2,.7,.5]);ref=np.array([0,1,0]);ap=np.array([[.2,.3],[.8,.7],[.4,.6]]);votes=(ap>=.5).astype(int)
    f0,d,s,c=feature_matrix(p,ref,ap,votes,False)
    f1,*_=feature_matrix(p,ref,ap,votes,True)
    assert f0.shape==(3,2) and f1.shape==(3,5)
    assert np.isclose(d[-1],.5)

def test_single_class_error_model_safe():
    x=np.ones((8,2));y=np.zeros(8,int)
    model=train_risk_model(x,y)
    assert np.all(predict_err(model,x)==0)
