"""Independent R6 case-level verifier. No training, no hyperparameter fitting.

Rebuilds threshold/tie decisions from frozen score files, switch set
confidence lower limits, accepted error costs, and manifest SHA-256s.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from switch_theory import paired_switch_summary,switch_set_certificate


def read(path):
    with open(path,newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def tie(z):
    h=hashlib.sha256(f'R6|61042|{z}'.encode('utf-8')).digest()
    return int.from_bytes(h[:8],'big')/2**64


def freeze(values,rate=.20):
    z=np.asarray(values,float);k=math.ceil(rate*len(z)-1e-12)
    t=float(np.sort(z)[-k]);equal=np.count_nonzero(z==t)
    return t,(k-np.count_nonzero(z>t))/equal


def review(scores,ids,thr):
    z=np.asarray(scores,float);t,p=thr
    return (z>t)|((z==t)&(np.array([tie(x) for x in ids])<p))


def check_close(a,b,tol=1e-12):
    if abs(float(a)-float(b))>tol:raise AssertionError(f'numeric mismatch {a} vs {b}')


def check(root:Path,protocol:Path):
    root=Path(root);p=json.loads(Path(protocol).read_text())
    assert p['id']=='R6_SWITCH_VALUE_AND_TRANSPORTABILITY_20261104'
    mani=json.loads((root/'R6_TEMPORAL_MANIFEST.json').read_text())
    assert mani['protocol_sha256']==hashlib.sha256(protocol.read_bytes()).hexdigest()
    for file,expected in mani['outputs_sha256'].items():
        assert hashlib.sha256((root/file).read_bytes()).hexdigest()==expected,file
    detail={(r['dataset'],r['model']):r for r in read(root/'R6_TEMPORAL_RESULTS.csv')}
    frozen={(r['dataset'],r['model']):r for r in read(root/'R6_CERTIFICATION.csv')}
    cert=defaultdict(list);test=defaultdict(list);thresholds=defaultdict(list)
    for r in read(root/'R6_CERTIFICATION_CASE_LEVEL.csv'):cert[r['dataset'],r['model']].append(r)
    for r in read(root/'R6_TEMPORAL_CASE_LEVEL.csv'):test[r['dataset'],r['model']].append(r)
    for r in read(root/'R6_THRESHOLD_CALIBRATION_SCORES.csv'):thresholds[r['dataset'],r['model']].append(r)
    metadata={tuple(x['cell'].split('/')):x for x in mani['cells']}
    n_cert=0;n_test=0
    assert len(detail)==len(cert)==len(test)==len(thresholds)==len(metadata)==8
    for key,saved in detail.items():
        cell_meta=metadata[key];tc=thresholds[key];certrows=cert[key];testrows=test[key]
        tb=freeze([float(z['base_error_risk_score']) for z in tc])
        ta=freeze([float(z['aug_error_risk_score']) for z in tc])
        for got,exp in zip(tb,cell_meta['base_threshold']):check_close(got,exp)
        for got,exp in zip(ta,cell_meta['aug_threshold']):check_close(got,exp)
        for rows in (certrows,testrows):
            ids=[r['time_id'] for r in rows]
            b=review([float(r['base_error_risk_score']) for r in rows],ids,tb)
            a=review([float(r['aug_error_risk_score']) for r in rows],ids,ta)
            assert np.array_equal(b,[bool(int(r['base_review'])) for r in rows]),key
            assert np.array_equal(a,[bool(int(r['aug_review'])) for r in rows]),key
        errs=np.array([int(r['reference_error']) for r in certrows])
        certcalc=switch_set_certificate(errs,np.array([int(r['base_review']) for r in certrows],bool),
            np.array([int(r['aug_review']) for r in certrows],bool),lam=.25,alpha=.05)
        v=frozen[key]
        check_close(certcalc['lower_gain_confidence'],v['lower_gain_confidence'])
        check_close(certcalc['empirical_gain'],v['empirical_gain'])
        assert int(certcalc['certified_positive'])==int(saved['cert_activated'])
        assert int(saved['certification_n'])==len(certrows)
        mask_b=np.array([int(r['base_review']) for r in testrows],bool)
        mask_a=np.array([int(r['aug_review']) for r in testrows],bool)
        err=np.array([int(r['reference_error']) for r in testrows],bool)
        c=paired_switch_summary(err,mask_b,mask_a,.25)
        check_close(c.gain,saved['aug_gain'])
        check_close(c.switch_fraction,saved['switch_frac'])
        def cost(m):return np.mean((err&~m).astype(float)+.25*m.astype(float))
        check_close(cost(mask_b),saved['base_cost']);check_close(cost(mask_a),saved['aug_cost'])
        g=mask_a if certcalc['certified_positive'] else mask_b
        assert np.array_equal(g,[bool(int(r['guard_review'])) for r in testrows])
        check_close(cost(g),saved['guard_cost'])
        assert len(testrows)==int(saved['test_n'])
        # Test labels were not needed to freeze any threshold or selector.
        assert len(set(r['time_id'] for r in tc) & set(r['time_id'] for r in certrows))==0
        assert len(set(r['time_id'] for r in tc) & set(r['time_id'] for r in testrows))==0
        assert len(set(r['time_id'] for r in certrows) & set(r['time_id'] for r in testrows))==0
        n_cert+=len(certrows);n_test+=len(testrows)
    out={'status':'INDEPENDENT_CASE_LEVEL_REPLAY_PASS','cells':len(detail),
         'certification_cases':n_cert,'heldout_cases':n_test,
         'validated':'thresholds, hash ties, masks, labels, cost deltas, certificates, disjoint case ids, manifest hashes'}
    (root/'R6_INDEPENDENT_RECOMPUTATION.json').write_text(json.dumps(out,indent=2)+'\n')
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    print(json.dumps(check(a.results,a.protocol)))

if __name__=='__main__':main()
