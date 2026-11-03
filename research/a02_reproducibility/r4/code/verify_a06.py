"""Independent read-only replay of every A06 decision from saved per-case scores."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from a06_streaming import POLICIES,freeze_threshold,stream_reject,batch_reject,metrics


def _same(a,b,atol=1e-11):
    if pd.isna(a) and pd.isna(b):return True
    if isinstance(a,(int,float,np.number)) and isinstance(b,(int,float,np.number)):
        return np.isclose(a,b,atol=atol,rtol=0)
    return str(a)==str(b)


def verify(protocol_path,folders):
    protocol_bytes=protocol_path.read_bytes()
    p=json.loads(protocol_bytes); hash_=hashlib.sha256(protocol_bytes).hexdigest()
    seen=set();total_case=0;outcomes=0;cells=0;errors=[]
    for root in folders:
        manifest=json.loads((root/'A06_MANIFEST.json').read_text())
        assert manifest['protocol_sha256']==hash_
        for name,digest in manifest['output_sha256'].items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, (root,name)
        raw=pd.read_csv(root/'A06_CASE_LEVEL.csv',float_precision='round_trip')
        outcomes_df=pd.read_csv(root/'A06_SUMMARY.csv',float_precision='round_trip')
        calibration_df=pd.read_csv(root/'A06_CALIBRATION.csv',float_precision='round_trip')
        total_case+=len(raw)
        assert not raw.duplicated(['cell','partition','case_id']).any()
        for key,sub in raw.groupby('cell',sort=True):
            if key in seen: raise AssertionError(f'duplicate cell {key}')
            seen.add(key);cells+=1
            va=sub[sub.partition=='validation'].sort_values('case_id')
            te=sub[sub.partition=='heldout'].sort_values('case_id')
            assert len(va)>4 and len(te)>4
            assert set(va.case_id).isdisjoint(te.case_id)
            if sub.dataset.iloc[0].startswith('modechoice'):
                assert set(va.group_id.dropna()).isdisjoint(te.group_id.dropna())
            truth=te.truth.to_numpy(dtype=int);yp=te.prediction.to_numpy(dtype=int);ids=te.case_id.to_numpy(dtype=int)
            for pol in POLICIES:
                score_val=va[f'score_{pol}'].to_numpy(dtype=float)
                score_te=te[f'score_{pol}'].to_numpy(dtype=float)
                cfg=freeze_threshold(score_val,p['target_coverage'])
                c_row=calibration_df[(calibration_df.cell==key)&(calibration_df.policy==pol)]
                assert len(c_row)==1
                c_row=c_row.iloc[0]
                for nm,val in cfg.items():
                    if not _same(val,c_row[nm]):errors.append((key,pol,'calibration',nm,val,c_row[nm]))
                rows=outcomes_df[(outcomes_df.cell==key)&(outcomes_df.policy==pol)]
                assert len(rows)==len(p['tie_seeds'])+1
                for _,r in rows.iterrows():
                    tie_seed=int(r['tie_seed'])
                    if r['evaluation']=='streaming_frozen': reject=stream_reject(score_te,ids,cfg,tie_seed)
                    elif r['evaluation']=='batch_exact_secondary':reject=batch_reject(score_te,ids,p['target_coverage'],tie_seed)
                    else:raise ValueError('invalid evaluation')
                    m=metrics(truth,yp,reject)
                    for name,val in m.items():
                        if not _same(val,r[name]):errors.append((key,pol,r['evaluation'],name,val,r[name]))
                    outcomes+=1
    if errors: raise AssertionError(str(errors[:20]))
    assert cells==4*2*4, cells
    assert outcomes==cells*len(POLICIES)*(len(p['tie_seeds'])+1), outcomes
    return {'status':'INDEPENDENT_RECOMPUTATION_PASS','cells':cells,'outcomes':outcomes,
            'case_rows':total_case,'protocol_sha256':hash_}


def main():
    ar=argparse.ArgumentParser();ar.add_argument('--protocol',type=Path,required=True)
    ar.add_argument('--results',type=Path,required=True)
    args=ar.parse_args();folders=[args.results/x for x in ['fair','randhie','modechoice','anes']]
    result=verify(args.protocol,folders)
    (args.results/'A06_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
