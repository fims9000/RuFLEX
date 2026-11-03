"""Independent read-only recomputation of A03 scores, policy rankings and reported outcomes.

Does not import the A03 execution module, except standard NumPy. Tests all saved
case rows, not summary-table hashes alone. Sample labels are not used in ranking.
"""
from __future__ import annotations
import csv,hashlib,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np


def rows(p):
    with open(p,encoding='utf-8',newline='') as fh: return list(csv.DictReader(fh))

def h(row_id,seed):
    return int(hashlib.sha256(f'{seed}:{row_id}'.encode()).hexdigest()[:16],16)


def select_unlabeled(ranks,ids,coverage,seed):
    k=math.ceil((1-coverage)*len(ids)-1e-12)
    order=sorted(range(len(ids)),key=lambda i:(-ranks[i],h(ids[i],seed)))
    return set(order[:k])


def close(a,b,tol=1e-10):
    return math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol)


def check_one(out_dir:Path,protocol_path:Path)->dict:
    p=json.loads(protocol_path.read_text());receipt=json.loads((out_dir/'A03_RECEIPT.json').read_text())
    assert receipt['protocol_sha256']==hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    for path,digest in receipt['files_sha256'].items():
        assert hashlib.sha256((out_dir/path).read_bytes()).hexdigest()==digest,(out_dir,path)
    observed=rows(out_dir/'A03_CASE_LEVEL.csv');summary=rows(out_dir/'A03_POLICY_OUTCOMES.csv');tie=rows(out_dir/'A03_TIE_SENSITIVITY.csv')
    cases=defaultdict(lambda:defaultdict(list))
    for row in observed:
        cases[row['cell_key']][row['partition']].append(row)
        assert int(row['reference_error'])==(int(row['truth'])!=int(row['reference_prediction']))
        conf=float(row['ref_confidence']);agree=float(row['observed_agreement']);std=float(row['prob_std'])
        assert .5-1e-12<=conf<=1+1e-12 and 0<=agree<=1 and 0<=std<=.500001
        assert close(agree*int(row['n_audit']),round(agree*int(row['n_audit'])))
        expected=dict(confidence_only=1-conf,disagreement_only=1-agree,
          combined_fixed=(1-conf)+.5*(1-agree),dispersion_fixed=(1-conf)+.5*std)
        for key,value in expected.items():assert close(row[f'score_{key}'],value),(row['cell_key'],key)
    assert len(cases)==receipt['n_completed_cells'] and len(observed)==receipt['n_case_records']
    sums={(r['cell_key'],float(r['budget']),r['policy']):r for r in summary}
    ties={(r['cell_key'],int(r['tie_seed']),r['policy']):r for r in tie}
    for cell,parts in cases.items():
        assert set(parts)=={'validation','heldout'}
        va=parts['validation'];te=parts['heldout']
        assert not set(x['case_id'] for x in va)&set(x['case_id'] for x in te)
        ids=[int(r['case_id']) for r in te]
        err=[int(r['reference_error']) for r in te]
        errors_all=sum(err)
        for budget in p['budgets']:
            baseline=None
            for name in p['policies']:
                key=(cell,float(budget),name);r=sums[key]
                review=select_unlabeled([float(x[f'score_{name}']) for x in te],ids,budget,0)
                n_review=len(review);n_acc=len(te)-n_review
                n_errors=sum(v for i,v in enumerate(err) if i not in review)
                n_review_errors=sum(v for i,v in enumerate(err) if i in review)
                assert int(r['n_review'])==n_review and int(r['n_accepted'])==n_acc
                assert int(r['accepted_errors'])==n_errors and int(r['reviewed_errors'])==n_review_errors
                assert int(r['error_count'])==errors_all
                assert close(r['accepted_risk'],n_errors/n_acc)
                assert close(r['coverage'],n_acc/len(te))
                assert close(r['reference_accuracy'],1-errors_all/len(te))
                assert int(r['high_conf_unstable_val'])==sum(float(x['ref_confidence'])>=.9 and float(x['observed_agreement'])<.8 for x in va)
                assert int(r['high_conf_unstable_test'])==sum(float(x['ref_confidence'])>=.9 and float(x['observed_agreement'])<.8 for x in te)
                if name=='confidence_only':baseline=n_errors/n_acc
                assert close(r['delta_risk_vs_confidence'],n_errors/n_acc-baseline)
            if budget==p['primary_budget']:
                for seed in p['tie_sensitivity_seeds']:
                    c_review=select_unlabeled([float(x['score_confidence_only']) for x in te],ids,budget,seed)
                    c_risk=sum(v for i,v in enumerate(err) if i not in c_review)/(len(te)-len(c_review))
                    for name in p['policies']:
                        t=ties[(cell,seed,name)]
                        review=select_unlabeled([float(x[f'score_{name}']) for x in te],ids,budget,seed)
                        risk=sum(v for i,v in enumerate(err) if i not in review)/(len(te)-len(review))
                        assert close(t['accepted_risk'],risk)
                        assert close(t['delta_risk_vs_confidence'],risk-c_risk)
    return dict(cells=len(cases),case_rows=len(observed),policy_rows=len(summary),tie_rows=len(tie),
         independently_recomputed=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--parts',nargs='+',type=Path,required=True)
    a=parser.parse_args()
    print(json.dumps([check_one(part,a.protocol) for part in a.parts],indent=2))
