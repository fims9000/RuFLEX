"""Combine A02 exploratory slices into a portable, provenance-aware report."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def consolidate(parts: list[Path], output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    combined = []
    cases = []
    configs = set()
    for part in parts:
        summary_path = part / 'summary_validation.json'
        case_path = part / 'case_level_validation.csv'
        summary = json.loads(summary_path.read_text())
        signature = (summary['split_seed'], summary['n_fresh_seeds'], summary['alpha'],
                     summary['target'], summary['selection_rule'])
        configs.add(signature)
        combined.extend(summary['cells'])
        with case_path.open(newline='', encoding='utf-8') as file:
            cases.extend(list(csv.DictReader(file)))
    if len(configs) != 1:
        raise ValueError('A02 slices use incompatible fixed configurations')
    keys = [(c['dataset_id'], c['model_family']) for c in combined]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate dataset/model cell across A02 slices')
    assert len(cases) == sum(x['n_validation'] for x in combined)
    with (output / 'A02_CASE_LEVEL_VALIDATION.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(cases[0]))
        w.writeheader(); w.writerows(cases)
    table = []
    for cell in combined:
        count = cell['n_validation']
        table.append({'dataset_id':cell['dataset_id'],'model_family':cell['model_family'],
            'validation_n':count,'reference_validation_accuracy':cell['reference_accuracy_validation'],
            'high_confidence_n':cell['validation_high_confidence_count'],
            'high_confidence_unstable_n':cell['validation_hcir_count'],
            'high_confidence_instability_rate':cell['validation_hcir'],
            'pointwise_certified_n':cell['pointwise_certified_count'],
            'familywise_certified_n':cell['simultaneously_certified_count'],
            'familywise_certified_fraction':cell['simultaneously_certified_count']/count})
    with (output / 'A02_VALIDATION_TABLE.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(table[0])); w.writeheader(); w.writerows(table)
    result = {
        'schema_version':1,'status':'EXPLORATORY_VALIDATION_ONLY',
        'source_protocol':'fresh independent-seed A02, NOT A01 frozen study',
        'a01_original_results_modified':False,
        'config_signature':{'split_seed':list(configs)[0][0], 'fresh_runs':list(configs)[0][1],
          'alpha':list(configs)[0][2],'target':list(configs)[0][3], 'selected_model_rule':list(configs)[0][4]},
        'data_count':len(set(c['dataset_id'] for c in combined)),
        'model_family_count':len(set(c['model_family'] for c in combined)),
        'cell_count':len(combined),
        'training_fits_including_references':sum(c['n_calibration_fits']+1 for c in combined),
        'validation_case_cell_pairs':len(cases),
        'familywise_certified_case_cell_pairs':sum(c['simultaneously_certified_count'] for c in combined),
        'pointwise_certified_case_cell_pairs':sum(c['pointwise_certified_count'] for c in combined),
        'high_confidence_unstable_case_cell_pairs':sum(c['validation_hcir_count'] for c in combined),
        'high_confidence_case_cell_pairs':sum(c['validation_high_confidence_count'] for c in combined),
        'case_evidence_sha256':sha256(output/'A02_CASE_LEVEL_VALIDATION.csv'),
        'tables_sha256':sha256(output/'A02_VALIDATION_TABLE.csv'),
        'table':table,
    }
    (output/'A02_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--parts',nargs='+',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=consolidate(a.parts,a.output)
    print({k:v for k,v in r.items() if k not in ('table','config_signature')})