"""Deterministic pre-execution feasibility check for an e-value alarm.

Maximum possible wealth is calculated by feeding x_t=1 for every step.
It is an algebraic upper bound, not a statistical power estimate. Under real
bounded gains, stochastic power can be much lower even if the cap is reachable.
"""
from __future__ import annotations
import json
from pathlib import Path
from evidence import mixture_path,STAKES


def maximum_mixture_e(steps,stakes=STAKES):
    if not isinstance(steps,int) or steps<0:raise ValueError('steps must be nonnegative integer')
    return float(mixture_path([1.0]*steps,stakes=stakes)[-1]) if steps else 1.


def minimum_steps_to_cross(alpha=.05,max_steps=10000,constant_gain=1.0):
    if not 0<alpha<1 or not 0<constant_gain<=1:raise ValueError('invalid alpha or gain')
    if max_steps<=0:raise ValueError('max_steps must be positive')
    # Every one of these observations must realize exactly the chosen gain.
    for n in range(1,max_steps+1):
        wealth=float(mixture_path([constant_gain]*n)[-1])
        if wealth>=1/alpha:return n
    return None


def run(protocol,out):
    protocol=json.load(open(protocol));out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    mon=protocol['slices_t_inclusive']['labelled_target_monitoring']
    n=mon[1]-mon[0]+1
    alpha=protocol['evalue']['alpha']
    threshold=1/alpha
    result={'years':n,'threshold':threshold,'absolute_maximum_mixture_e':maximum_mixture_e(n),
        'any_alarm_mathematically_possible':maximum_mixture_e(n)>=threshold,
        'minimum_years_to_alarm_under_all_maximum_gains':minimum_steps_to_cross(alpha),
        'minimum_years_to_alarm_under_constant_gains':{
            str(v):minimum_steps_to_cross(alpha,constant_gain=v)
            for v in [0.05,0.075,0.1,0.25,0.5]},
        'finding':'original six-year R7 annual gate is structurally unable to cross the threshold, even under all x_t=+1',
        'status':'power feasibility correction after local protocol freeze; never interpret 0/4 activations as evidence of safety or sufficient monitoring'}
    out.write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=Path(__file__).parent.parent
    print(json.dumps(run(p/'PROTOCOL_R7.json',p/'results/analysis/R7_FEASIBILITY.json'),indent=2))
