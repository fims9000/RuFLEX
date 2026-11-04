"""R6: controllable mechanism experiment with an EXACT population oracle.

These synthetic Bernoulli worlds are not experiments with retrained ML models.
They isolate policy-switch estimation, finite-sample certification, and
unidentifiable label drift while keeping the entire observable Z distribution
unchanged. Protocol and RNG are externally inspectable.
"""
from __future__ import annotations
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
from scipy.stats import beta
from switch_theory import switch_set_certificate

SCENARIOS=('actionable','neutral','nonactionable','wrong_signal','invisible_reversal')
CERT_SIZES=(100,400,1600,6400)

def world(scenario:str):
    if scenario=='actionable':
        return np.array([[.05,.05],[.05,.75]]),np.array([[.05,.05],[.05,.75]]),'source_actionable'
    if scenario=='invisible_reversal':
        return np.array([[.05,.05],[.05,.75]]),np.array([[.05,.05],[.75,.05]]),'unobserved_concept_shift'
    if scenario=='neutral':
        return np.array([[.30,.30],[.30,.30]]),np.array([[.30,.30],[.30,.30]]),'no_risk_difference'
    if scenario=='nonactionable':
        return np.array([[.05,.15],[.10,.20]]),np.array([[.05,.15],[.10,.20]]),'risk_dependence_but_no_action'
    if scenario=='wrong_signal':
        return np.array([[.05,.05],[.40,.40]]),np.array([[.05,.05],[.40,.40]]),'disagreement_uninformative_within_confidence'
    raise ValueError(scenario)


def decisions(scenario,confidence_group,disagreement):
    c=np.asarray(confidence_group,int)
    d=np.asarray(disagreement,int)
    if scenario in ('actionable','invisible_reversal'):
        baseline=(c==1)
        augmented=(c==1)&(d==1)
    elif scenario=='neutral':
        baseline=(c==1)
        augmented=(d==1)
    elif scenario=='nonactionable':
        baseline=np.zeros(len(c),bool)
        augmented=np.zeros(len(c),bool)
    elif scenario=='wrong_signal':
        baseline=(c==1)
        augmented=(d==1)
    else:raise ValueError(scenario)
    return baseline,augmented


def oracle_gain(scenario,risk,lam=.25):
    groups=np.array([0,0,1,1]);signal=np.array([0,1,0,1])
    b,a=decisions(scenario,groups,signal)
    return float(.25*np.sum((a.astype(int)-b.astype(int))*(risk[groups,signal]-lam)))


def sample_cert(rng,scenario,risk,n):
    z=rng.integers(0,2,size=(n,2))
    b,a=decisions(scenario,z[:,0],z[:,1])
    e=(rng.random(n)<risk[z[:,0],z[:,1]]).astype(int)
    return e,b,a


def write_rows(path,rows):
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)


def experiment(n_reps=200,seed=20261104,alpha=.05,lam=.25):
    rng=np.random.default_rng(seed)
    rows=[]
    for name in SCENARIOS:
        source,target,mechanism=world(name)
        gs=oracle_gain(name,source,lam);gt=oracle_gain(name,target,lam)
        for n in CERT_SIZES:
            for rep in range(n_reps):
                e,b,a=sample_cert(rng,name,source,n)
                c=switch_set_certificate(e,b,a,lam=lam,alpha=alpha)
                active=int(c['certified_positive'])
                rows.append({'scenario':name,'mechanism':mechanism,'cert_n':n,'replicate':rep,
                  'source_oracle_gain':gs,'target_oracle_gain':gt,
                  'observed_cert_gain':c['empirical_gain'],
                  'cert_lower_bound':c['lower_gain_confidence'],
                  'candidate_activated':active,
                  'actual_target_gain_if_activated':active*gt,
                  'source_identical_to_target':int(np.array_equal(source,target)),
                  'unlabeled_z_distinguishable':0})
        print(name,'true source/target gains',round(gs,5),round(gt,5),flush=True)
    summary=[]
    for name in SCENARIOS:
        for n in CERT_SIZES:
            sub=[r for r in rows if r['scenario']==name and r['cert_n']==n]
            positives=sum(t['candidate_activated'] for t in sub);num=len(sub)
            a=alpha/2
            lo=float(beta.ppf(a,positives,num-positives+1)) if positives else 0.
            hi=float(beta.ppf(1-a,positives+1,num-positives)) if positives<num else 1.
            summary.append({'scenario':name,'cert_n':n,'replicates':num,
                'source_oracle_gain':sub[0]['source_oracle_gain'],
                'target_oracle_gain':sub[0]['target_oracle_gain'],
                'certification_rate':positives/num,
                'rate_ci95_low':lo,'rate_ci95_high':hi,
                'mean_realized_target_gain':np.mean([t['actual_target_gain_if_activated'] for t in sub]),
                'source_identical_to_target':sub[0]['source_identical_to_target'],
                'unlabeled_shift_detection_possible':False})
    return rows,summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    raw=a.protocol.read_bytes();protocol=json.loads(raw)
    assert protocol['id']=='R6_SWITCH_VALUE_AND_TRANSPORTABILITY_20261104'
    a.out.mkdir(parents=True,exist_ok=True)
    reps,summary=experiment()
    write_rows(a.out/'R6_SIMULATION_REPLICATES.csv',reps)
    write_rows(a.out/'R6_SIMULATION_SUMMARY.csv',summary)
    (a.out/'R6_SIMULATION_RECEIPT.json').write_text(json.dumps({
        'protocol_sha256':hashlib.sha256(raw).hexdigest(),
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'worlds':'2x2 mutually exclusive observable classes and disagreement groups, each probability 1/4',
        'known_error_risks':'explicit 2x2 tables in world()',
        'replicates':len(reps),'scenarios':len(SCENARIOS),'certificate_sizes':CERT_SIZES,
        'output_sha256':{n:hashlib.sha256((a.out/n).read_bytes()).hexdigest() for n in ('R6_SIMULATION_REPLICATES.csv','R6_SIMULATION_SUMMARY.csv')},
        'scope':'synthetic mechanism check, not new empirical ML domain'},indent=2)+'\n')

if __name__=='__main__':main()
