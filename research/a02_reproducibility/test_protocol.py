"""Negative and replay checks for split provenance and output integrity."""
from pathlib import Path
import csv
import json
import numpy as np
import pytest
from sklearn.datasets import make_classification
from benchmark import split_and_normalize, run_benchmark
from verify_experiment import inspect_partial


def test_two_splits_differ_without_changing_lengths():
    x, y = make_classification(n_samples=500, n_features=8, n_informative=5, random_state=7)
    a = split_and_normalize(x, y, split_seed=42)
    b = split_and_normalize(x, y, split_seed=73)
    assert a[0].shape == b[0].shape == (300, 8)
    assert a[2].shape == b[2].shape == (100, 8)
    assert set(a[4]).isdisjoint(set(a[5])) and set(a[4]).isdisjoint(set(a[6]))
    assert not np.array_equal(np.sort(a[5]), np.sort(b[5]))
    assert np.max(np.abs(np.mean(a[0],axis=0))) < 1e-12
    assert np.allclose(a[0].std(axis=0),1)


def test_reject_seed_overlap(tmp_path):
    with pytest.raises(ValueError,match='overlaps'):
        run_benchmark(tmp_path,mode='bundled',n_seeds=2,families=('decision_tree',),
                      split_seed=4,reference_seed=100, fresh_seed_start=100)


def test_small_benchmark_replays(tmp_path):
    one=tmp_path/'one';two=tmp_path/'two'
    kw={'mode':'bundled','families':('decision_tree',),'n_seeds':2,
        'split_seed':73,'reference_seed':27000,'fresh_seed_start':30000}
    a=run_benchmark(one,**kw);b=run_benchmark(two,**kw)
    assert a['fit_count']==b['fit_count']==9
    assert a['final_test_used'] is False
    assert [x['validation_indices_sha256'] for x in a['cells']]==[x['validation_indices_sha256'] for x in b['cells']]
    assert (one/'case_level_validation.csv').read_bytes()==(two/'case_level_validation.csv').read_bytes()
    check=inspect_partial(one)
    assert check['fits']==9 and check['cells']==3


def test_integrity_detects_mutation(tmp_path):
    run_benchmark(tmp_path,mode='bundled',families=('decision_tree',),n_seeds=2)
    p=tmp_path/'case_level_validation.csv'
    original=p.read_text()
    p.write_text(original.replace(',False,',',True,',1))
    with pytest.raises(AssertionError):
        inspect_partial(tmp_path)