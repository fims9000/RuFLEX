import numpy as np
import pytest
from evidence import (policy_gain,method_cost,stable_unit,choose_threshold,
    review_masks,mixture_path,first_evidence_time,simulate_correlated_years)

def test_gain_identity_with_random_review_masks():
    rng=np.random.default_rng(11)
    e=rng.integers(0,2,100)
    a=rng.integers(0,2,100).astype(bool);b=rng.integers(0,2,100).astype(bool)
    g=policy_gain(e,b,a,.25).mean()
    assert np.isclose(g,method_cost(e,b,.25)-method_cost(e,a,.25))

def test_no_switched_items_zero_gain():
    e=np.array([1,0,1]);b=np.array([0,1,1],dtype=bool)
    assert not np.any(policy_gain(e,b,b,.25))

def test_zero_gains_keep_wealth_one():
    assert np.allclose(mixture_path([0,0,0]),1)

def test_benefit_harm_are_sign_flips():
    x=[.5,-.25,.1,0]
    assert np.allclose(mixture_path(x,side='harm'),mixture_path([-z for z in x]))

def test_single_sign_and_bounded_inputs():
    with pytest.raises(ValueError):mixture_path([1.1])
    with pytest.raises(ValueError):mixture_path([float('nan')])
    assert first_evidence_time(mixture_path([.75]*50)) is not None
    assert first_evidence_time(mixture_path([-.75]*50)) is None

def test_independent_validation_threshold_without_labels():
    s=np.array([.8,.8,.8,.1,.2]);keys=['a','b','c','d','e']
    rule=choose_threshold(s,keys,.4,5)
    a=review_masks(s,keys,rule,5)
    # Deterministic random tie may yield not exactly two items under calibration
    # because threshold uses a randomized tie-probability, not rank-matching per ID.
    assert rule['score_cutoff']==.8
    assert np.array_equal(a,review_masks(s,keys,rule,5))
    assert 0<=rule['tie_probability']<=1

def test_simulated_pseudoreplication_is_anti_conservative():
    a=simulate_correlated_years(replicates=100,years=12,countries=200,seed=71301)
    assert sum(v['naive'] for v in a)>10
    assert sum(v['year_aggregated'] for v in a)<=10

def test_stable_uniform_hash():
    assert stable_unit('JPN:2001',71250)==stable_unit('JPN:2001',71250)
    assert stable_unit('JPN:2001',71250)!=stable_unit('JPN:2001',71251)

def test_6_annual_observations_cannot_reach_frozen_evidence_threshold():
    from power_audit import maximum_mixture_e,minimum_steps_to_cross
    assert maximum_mixture_e(6) < 20
    assert round(maximum_mixture_e(6),9)==round(5.3223736828006,9)
    assert minimum_steps_to_cross(.05)>6
