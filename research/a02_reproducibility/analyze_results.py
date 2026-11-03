"""Generate data-only exploratory tables from A02 case-level evidence.

All effect summaries are descriptive; no independent-case uncertainty is asserted
when the same validation subjects recur across model families.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from collections import defaultdict


def load_rows(paths):
    data=[]
    for p in paths:
        with Path(p).open(newline='',encoding='utf-8') as h:
            data.extend(csv.DictReader(h))
    for x in data:
        x.update({'confidence':float(x['confidence']),
                  'observed_agreement':float(x['observed_agreement']),
                  'error':int(x['reference_error']),
                  'certified':x['simultaneous_certified'].lower()=='true'})
    return data


def count(group):
    high=[z for z in group if z['confidence']>=.9]
    hu=[z for z in high if z['observed_agreement']<.8]
    hs=[z for z in high if z['observed_agreement']>=.8]
    certified=[z for z in group if z['certified']]
    notcert=[z for z in group if not z['certified']]
    return {
      'n':len(group),
      'high_confidence_n':len(high),
      'hcir_n':len(hu),
      'hcir_fraction':len(hu)/len(high) if high else None,
      'hcir_errors_n':sum(z['error'] for z in hu),
      'hcir_error_rate':sum(z['error'] for z in hu)/len(hu) if hu else None,
      'high_stable_n':len(hs),
      'high_stable_errors_n':sum(z['error'] for z in hs),
      'high_stable_error_rate':sum(z['error'] for z in hs)/len(hs) if hs else None,
      'certified_n':len(certified),
      'certified_errors_n':sum(z['error'] for z in certified),
      'certified_error_rate':sum(z['error'] for z in certified)/len(certified) if certified else None,
      'not_certified_n':len(notcert),
      'not_certified_errors_n':sum(z['error'] for z in notcert),
      'not_certified_error_rate':sum(z['error'] for z in notcert)/len(notcert) if notcert else None,
    }


def summarize(rows,split):
    grouped=defaultdict(list)
    for x in rows:
        grouped[(x['dataset_id'],x['model_family'])].append(x)
    for group in grouped.values():
        if len(group)!=len({x['case_id'] for x in group}):
            raise ValueError('Duplicate cases')
    out=[]
    for (ds,model),group in sorted(grouped.items()):
        out.append({'split_seed':split,'dataset_id':ds,'model_family':model,**count(group)})
    return out


def save_table(path, rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split42',type=Path,required=True)
    parser.add_argument('--split73',nargs=2,type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    a=summarize(load_rows([args.split42]),42)
    b=summarize(load_rows(args.split73),73)
    names={row['model_family'] for row in b}
    shared=[x for x in a if x['model_family'] in names]
    if sorted((r['dataset_id'],r['model_family']) for r in shared)!=sorted((r['dataset_id'],r['model_family']) for r in b):
        raise ValueError('Split cross-match mismatch')
    per_cell=a+b
    save_table(args.output/'A02_ERROR_ENRICHMENT_AND_SPLIT_SENSITIVITY.csv',per_cell)
    aggregate={}
    for key,rows in [(42,shared),(73,b)]:
        for model in sorted(names):
            x=[r for r in rows if r['model_family']==model]
            aggregate[(key,model)]={'split_seed':key,'model_family':model,
              'n':sum(r['n'] for r in x),
              'high_confidence_n':sum(r['high_confidence_n'] for r in x),
              'hcir_n':sum(r['hcir_n'] for r in x),
              'hcir_errors_n':sum(r['hcir_errors_n'] for r in x),
              'high_stable_n':sum(r['high_stable_n'] for r in x),
              'high_stable_errors_n':sum(r['high_stable_errors_n'] for r in x),
              'certified_n':sum(r['certified_n'] for r in x),
              'certified_errors_n':sum(r['certified_errors_n'] for r in x),
              'not_certified_n':sum(r['not_certified_n'] for r in x),
              'not_certified_errors_n':sum(r['not_certified_errors_n'] for r in x)}
    summary=[]
    for z in aggregate.values():
        z['hcir_error_rate']=z['hcir_errors_n']/z['hcir_n'] if z['hcir_n'] else None
        z['high_stable_error_rate']=z['high_stable_errors_n']/z['high_stable_n'] if z['high_stable_n'] else None
        z['high_confidence_instability_rate']=z['hcir_n']/z['high_confidence_n'] if z['high_confidence_n'] else None
        z['certified_fraction']=z['certified_n']/z['n']
        summary.append(z)
    summary.sort(key=lambda x:(x['split_seed'],x['model_family']))
    save_table(args.output/'A02_SPLIT_COMPARISON.csv',summary)
    (args.output/'A02_SPLIT_COMPARISON.json').write_text(json.dumps({'status':'POST_HOC_EXPLORATORY_SPLIT_SENSITIVITY',
        'interpretation':'Descriptive only, no confidence intervals over cases or independent dataset replication',
        'analysis_cell_count':len(per_cell),
        'split42_additional_cells':len(shared),
        'split73_additional_cells':len(b),
        'rows':summary},indent=2)+'\n')
    print('Additional split summary:')
    for x in summary:
        print(x['split_seed'],x['model_family'],'HCIR',x['hcir_n'],'/',x['high_confidence_n'],
              'error rates',x['hcir_error_rate'],x['high_stable_error_rate'],
              'cert',x['certified_n'],'/',x['n'])

if __name__=='__main__':main()