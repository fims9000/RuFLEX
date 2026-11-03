"""Arithmetic invariants for A06 supplementary review-cost sensitivity."""
from pathlib import Path
from a06_review_cost import compute, LAMBDA_GRID

ROOT=Path(__file__).resolve().parent.parent

def test_grid_has_complete_cells():
    t,s=compute(ROOT/'results')
    assert len(t)==32*len(LAMBDA_GRID)
    assert len(s)==len(LAMBDA_GRID)
    assert (s['improved']+s['tied']+s['worsened']).eq(32).all()

def test_cost_formula_and_linear_gap():
    t,_=compute(ROOT/'results')
    assert abs(t['delta_cost_per_100']-(t['delta_auto_errors_per_100']+
              t['lambda_review_per_error']*t['delta_reviews_per_100'])).max()<1e-10

def test_zero_cost_counts_only_automated_errors():
    t,_=compute(ROOT/'results')
    q=t[t.lambda_review_per_error==0]
    assert len(q)==32
    assert (q['delta_cost_per_100']-q['delta_auto_errors_per_100']).abs().max()<1e-12

def test_pareto_category_partition():
    t,_=compute(ROOT/'results')
    q=t[t.lambda_review_per_error==0]
    assert q.pareto_category.value_counts().to_dict()=={
        'TRADEOFF':18,'SAME':8,'PARETO_BETTER':5,'PARETO_WORSE':1}
