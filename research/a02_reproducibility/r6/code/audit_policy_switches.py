"""R6 retrospective case-level switch audit of completed A06 and R5 studies.

Labels have already been inspected in both studies: results are descriptive,
not pre-registered confirmations. Policy decisions are reconstructed without
looking at held-out labels; every reconstructed R4 outcome is checked against
frozen historical summaries for tie_seed=1 before any R6 table is written.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from collections import defaultdict

import numpy as np
from switch_theory import paired_switch_summary


def read_csv(p):
    with Path(p).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def write_csv(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def tie_uniform_a06(ids,seed=1):
    return np.array([int.from_bytes(hashlib.sha256(f'a06|{seed}|{int(t)}'.encode('ascii')).digest()[:8],'big')/2**64 for t in ids])


def r4_review(scores,ids,policy,mode='stream',coverage=.90):
    z=np.asarray(scores,float)
    u=tie_uniform_a06(ids,1)
    if mode=='stream':
        threshold=float(policy['threshold']);tp=float(policy['tie_rejection_probability'])
        return (z>threshold)|((z==threshold)&(u<tp))
    k=math.ceil((1-coverage)*len(z)-1e-12)
    order=np.lexsort((u,-z));rev=np.zeros(len(z),dtype=bool);rev[order[:k]]=True
    return rev


def cell_record(study,dataset,cell,model,fold,mode,lam,e,b,a):
    s=paired_switch_summary(e,b,a,lam)
    e=np.asarray(e,int);b=np.asarray(b,bool);a=np.asarray(a,bool)
    extra=a&~b;lost=b&~a
    diff_review=int(np.sum(a)-np.sum(b))
    # Positive new error catches minus errors released.
    new_err_minus_lost=s.extra_review_errors-s.released_errors
    # Cost-neutral point if review workloads differ.
    cost_break_even=(new_err_minus_lost/diff_review if diff_review else None)
    return dict(study=study,dataset=dataset,cell=cell,model=model,fold=fold,mode=mode,
        n=s.n,error_n=int(e.sum()),baseline_review_n=s.base_reviews,augmented_review_n=s.augmented_reviews,
        extra_review_n=s.extra_reviewed,released_n=s.released_from_review,
        switches_n=s.extra_reviewed+s.released_from_review,switch_fraction=s.switch_fraction,
        extra_review_error_n=s.extra_review_errors,released_error_n=s.released_errors,
        extra_review_error_rate=float(e[extra].mean()) if extra.any() else None,
        released_error_rate=float(e[lost].mean()) if lost.any() else None,
        net_errors_avoided=new_err_minus_lost,
        gain_per_case=s.gain,cost_lambda=lam,break_even_cost=cost_break_even,
        epsilon_to_erase_positive_gain=s.fragility_epsilon if s.gain>0 else None,
        sensitivity_one_adversarial_error=bool(s.gain>0 and s.gain*s.n<=1+1e-12),
        invariant_fraction=1-s.switch_fraction)


def load_a06(r4_root:Path,lam):
    source=r4_root/'results'
    summary=[]
    for dirname in ('fair','randhie','modechoice','anes'):
        rows=read_csv(source/dirname/'A06_CASE_LEVEL.csv')
        thresholds=read_csv(source/dirname/'A06_CALIBRATION.csv')
        frozen=read_csv(source/dirname/'A06_SUMMARY.csv')
        cfg={(r['cell'],r['policy']):r for r in thresholds}
        check={(r['cell'],r['policy'],r['evaluation'],str(r['tie_seed'])):r for r in frozen}
        cells=defaultdict(list)
        for row in rows:
            if row['partition']=='heldout':cells[row['cell']].append(row)
        for cell,g in cells.items():
            ids=np.array([int(r['case_id']) for r in g]);e=np.array([int(r['truth'])!=int(r['prediction']) for r in g])
            # preserve frozen case order; tied ordering is deterministic by case id
            bscore=[float(r['score_confidence_only']) for r in g]
            ascore=[float(r['score_combined_fixed']) for r in g]
            for mode,ev in [('stream','streaming_frozen'),('batch','batch_exact_secondary')]:
                b=r4_review(bscore,ids,cfg[cell,'confidence_only'],mode)
                a=r4_review(ascore,ids,cfg[cell,'combined_fixed'],mode)
                for policy,mask in [('confidence_only',b),('combined_fixed',a)]:
                    old=check.get((cell,policy,ev,'1'))
                    if old is None:raise ValueError('missing historical comparison '+str((cell,policy,ev)))
                    if int(old['reviewed'])!=int(mask.sum()) or int(old['accepted_errors'])!=int((e&~mask).sum()):
                        raise AssertionError('Mismatch with frozen A06 evidence '+cell+policy+ev)
                r=g[0]
                summary.append(cell_record('A06','A06/'+r['dataset'],cell,r['model'],str(r['split_seed']),mode,lam,e,b,a))
    return summary


def load_r5(co2_file,lam):
    rows=read_csv(co2_file);cells=defaultdict(list)
    for r in rows:cells[r['cell']].append(r)
    out=[]
    for cell,g in cells.items():
        e=np.array([int(r['reference_is_wrong']) for r in g]);r=g[0]
        for mode,tag in [('stream','stream'),('batch','batch')]:
            b=np.array([int(t['review_calibrated_confidence_'+tag]) for t in g],bool)
            a=np.array([int(t['review_calibrated_conditional_'+tag]) for t in g],bool)
            if mode=='batch' and b.sum()!=a.sum():raise AssertionError('batch review quotas differ')
            out.append(cell_record('R5','R5/CO2',cell,r['model'],r['fold'],mode,lam,e,b,a))
    return out


def summarize_by_domain(records):
    # dataset is independent unit; models/folds depend and should NOT form a pooled n.
    by=defaultdict(list)
    for r in records:by[(r['study'],r['dataset'],r['mode'])].append(r)
    out=[]
    for (study,dataset,mode),g in sorted(by.items()):
        gains=np.array([x['gain_per_case'] for x in g])
        sw=np.array([x['switch_fraction'] for x in g]);pos=np.array([x['epsilon_to_erase_positive_gain'] for x in g if x['epsilon_to_erase_positive_gain'] is not None])
        out.append(dict(study=study,dataset=dataset,mode=mode,cells=len(g),improved=int((gains>1e-12).sum()),
            tied=int((abs(gains)<=1e-12).sum()),worsened=int((gains<-1e-12).sum()),
            descriptive_mean_gain=float(gains.mean()),descriptive_mean_switch_fraction=float(sw.mean()),
            median_positive_robustness_radius=float(np.median(pos)) if len(pos) else None))
    return out


def run(a06_root,co2_file,out,lam):
    result=load_a06(Path(a06_root),lam)+load_r5(co2_file,lam)
    assert len(result)==80,(len(result),'expected 32*2+8*2')
    write_csv(Path(out)/'R6_POLICY_SWITCH_CELLS.csv',result)
    domains=summarize_by_domain(result)
    write_csv(Path(out)/'R6_DOMAIN_SUMMARY.csv',domains)
    by_mode={}
    for mode in ('stream','batch'):
        items=[r for r in result if r['mode']==mode]
        pos=[r for r in items if r['gain_per_case']>1e-12]
        by_mode[mode]={'cells':len(items),'improved':len(pos),'worsened':sum(r['gain_per_case']<-1e-12 for r in items),
            'tied':sum(abs(r['gain_per_case'])<=1e-12 for r in items),
            'mean_switch_fraction':float(np.mean([r['switch_fraction'] for r in items])),
            'positive_gain_one_case_fragile':sum(r['sensitivity_one_adversarial_error'] for r in pos),
            'median_positive_epsilon_flip':float(np.median([r['epsilon_to_erase_positive_gain'] for r in pos])) if pos else None}
    report={'method':'retrospective policy-switch identity; threshold replay verified against frozen A06 case-level evidence',
      'interpretation':'R4 and R5 labels had been inspected before R6. Descriptive, not confirmatory.',
      'lambda':lam,'cells_per_mode':40,'by_mode':by_mode,'by_domain':domains,
      'source_data_sha256':{
       'r5_case_level':hashlib.sha256(Path(co2_file).read_bytes()).hexdigest()}}
    Path(out,'R6_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--a06-root',type=Path,required=True)
    p.add_argument('--r5-case-level',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--lambda-review',type=float,default=.25)
    args=p.parse_args()
    print(json.dumps(run(args.a06_root,args.r5_case_level,args.out,args.lambda_review)['by_mode'],indent=2))

if __name__=='__main__':main()
