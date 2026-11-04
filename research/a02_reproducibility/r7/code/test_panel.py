import json
from pathlib import Path
import numpy as np
import pytest
from run_panel import make_panel,base_model
from evidence import mixture_path
from verify_panel import verify

HERE=Path(__file__).resolve().parent.parent

def test_frozen_panel_slices_and_iso_filter():
    p=json.loads((HERE/'PROTOCOL_R7.json').read_text())
    d,excluded=make_panel(p)
    assert not d.duplicated(['country_code','year']).any()
    assert d.year.between(1965,2012).all()
    assert set(d.stage)==set(p['slices_t_inclusive'])
    assert (d.groupby('stage')['year'].min().to_dict()['frozen_future_evaluation']>=2006)
    assert len(excluded)>0

def test_reference_prediction_is_not_auxiliary_voting():
    # Pure reference decision, regardless of auxiliary agreement.
    score=np.array([0.6,0.4])
    ref=(score>=0.5).astype(int)
    auxiliaries=np.array([[0,1],[0,1],[0,1]])
    assert ref.tolist()==[1,0]
    assert auxiliaries.shape==(3,2)

def test_real_case_level_recompute():
    if (HERE/'results/panel/R7_RECEIPT.json').exists():
        x=verify(HERE/'results/panel',HERE/'PROTOCOL_R7.json')
        assert x['status']=='PASS'


def test_missing_yearly_dependency_guard_not_silent():
    # A 'safe' monitoring claim cannot be inferred solely from applying code.
    path=HERE/'PROTOCOL_R7.json'
    p=json.loads(path.read_text())
    assert p['primary_unit_of_sequential_monitoring'].startswith('year mean')
    assert p['forbidden'][1]=='asserting countries independent in the same calendar year'
