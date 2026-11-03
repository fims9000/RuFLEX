"""Recompute A02 experiment summaries and statistical certificates from saved case rows.

No training, no A01 final-test access, and no unsupported inferential claims.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from math import isclose
from certificates import exact_one_sided_lower


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as fp:
        return list(csv.DictReader(fp))


def inspect_partial(part: Path) -> dict:
    root = Path(part)
    summary = json.loads((root / 'summary_validation.json').read_text())
    rows = read_csv(root / 'case_level_validation.csv')
    bycell = defaultdict(list)
    for r in rows:
        key = (r['dataset_id'], r['model_family'])
        bycell[key].append(r)
    expected = {(c['dataset_id'], c['model_family']): c for c in summary['cells']}
    if set(expected) != set(bycell):
        raise AssertionError(f'cell keys mismatch in {part}')
    alpha = float(summary['alpha'])
    target = float(summary['target'])
    n = int(summary['n_fresh_seeds'])
    if n < 1 or n > 512:
        raise AssertionError('invalid seed count')
    if summary.get('fit_count') != len(expected)*(n+1):
        raise AssertionError('fit count mismatch')
    for key, group in bycell.items():
        meta = expected[key]
        m = len(group)
        if m != meta['n_validation'] or len({row['case_id'] for row in group}) != m:
            raise AssertionError(f'duplicate or missing case IDs in {key}')
        if meta['n_train'] + meta['n_validation'] + meta['n_untouched_final_test'] < 1:
            raise AssertionError('missing split')
        if meta['reference_seed'] in range(meta['fresh_seed_range'][0],meta['fresh_seed_range'][1]+1):
            raise AssertionError('reference in calibration seeds')
        if meta['fresh_seed_range'][1]-meta['fresh_seed_range'][0]+1 != n:
            raise AssertionError('wrong calibration seeds')
        counts={'hi':0,'unstable':0,'pointwise':0,'simul':0,'correct':0}
        for row in group:
            k = int(row['agreements'])
            observed = float(row['observed_agreement'])
            if int(row['n_runs']) != n or not 0 <= k <= n or not isclose(observed, k/n, abs_tol=1e-12):
                raise AssertionError('invalid count/agreement')
            pt = exact_one_sided_lower(k,n,alpha)
            family = exact_one_sided_lower(k,n,alpha/m)
            if not isclose(float(row['pointwise_lower']), pt,abs_tol=1e-12):
                raise AssertionError(f'pointwise mismatch in {key}')
            if not isclose(float(row['simultaneous_lower']),family,abs_tol=1e-12):
                raise AssertionError(f'Bonferroni mismatch in {key}')
            c = float(row['confidence'])
            if not (.5 <= c <= 1):
                raise AssertionError('confidence out of range')
            p=(row['pointwise_certified'].lower()=='true')
            f=(row['simultaneous_certified'].lower()=='true')
            if p != (pt >= target) or f != (family >= target) or (f and not p):
                raise AssertionError('certificate flags invalid')
            if int(row['reference_error']) != (int(row['reference_label']) != int(row['truth'])):
                raise AssertionError('incorrect error flag')
            counts['hi'] += c >= .9
            counts['unstable'] += c >= .9 and observed < .8
            counts['pointwise'] += p
            counts['simul'] += f
            counts['correct'] += 1-int(row['reference_error'])
        for field,val in [('validation_high_confidence_count',counts['hi']),
                          ('validation_hcir_count',counts['unstable']),
                          ('pointwise_certified_count',counts['pointwise']),
                          ('simultaneously_certified_count',counts['simul'])]:
            if meta[field] != val:
                raise AssertionError(f'{field} mismatch for {key}')
        if not isclose(meta['reference_accuracy_validation'],counts['correct']/m,abs_tol=1e-12):
            raise AssertionError(f'accuracy mismatch for {key}')
    return {'cells':len(expected),'cases':len(rows),'fits':len(expected)*(n+1),'sha256':hashlib.sha256((root/'case_level_validation.csv').read_bytes()).hexdigest()}


def inspect_combined(root: Path) -> dict:
    root=Path(root)
    summary=json.loads((root/'A02_SUMMARY.json').read_text())
    cells=read_csv(root/'A02_VALIDATION_TABLE.csv')
    cases=read_csv(root/'A02_CASE_LEVEL_VALIDATION.csv')
    if len(cells)!=summary['cell_count'] or len(cases)!=summary['validation_case_cell_pairs']:
        raise AssertionError('summary counts inconsistent')
    if sum(int(x['familywise_certified_n']) for x in cells)!=summary['familywise_certified_case_cell_pairs']:
        raise AssertionError('familywise counts inconsistent')
    if sum(int(x['pointwise_certified_n']) for x in cells)!=summary['pointwise_certified_case_cell_pairs']:
        raise AssertionError('pointwise counts inconsistent')
    if sum(int(x['high_confidence_unstable_n']) for x in cells)!=summary['high_confidence_unstable_case_cell_pairs']:
        raise AssertionError('high-confidence unstable counts inconsistent')
    if sum(int(x['high_confidence_n']) for x in cells)!=summary['high_confidence_case_cell_pairs']:
        raise AssertionError('high-confidence counts inconsistent')
    for path,key in [('A02_CASE_LEVEL_VALIDATION.csv','case_evidence_sha256'),('A02_VALIDATION_TABLE.csv','tables_sha256')]:
        digest=hashlib.sha256((root/path).read_bytes()).hexdigest()
        if digest != summary[key]:
            raise AssertionError(f'{path} digest changed')
    return {'cells':len(cells),'cases':len(cases),'fits':summary['training_fits_including_references'],'digest':summary['case_evidence_sha256']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parts',nargs='+',type=Path)
    parser.add_argument('--combined',type=Path)
    args=parser.parse_args()
    print(json.dumps({'partial':[inspect_partial(p) for p in args.parts or []],
                      'combined':inspect_combined(args.combined) if args.combined else None},indent=2))

if __name__=='__main__':
    main()