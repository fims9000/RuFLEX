"""R7 null experiment: effect of correlated within-year labels on betting tests."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from evidence import simulate_correlated_years,mixture_path,first_evidence_time


def run(out, reps=1000):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    records=simulate_correlated_years(replicates=reps,years=12,countries=200,seed=71301)
    df=pd.DataFrame(records)
    df.to_csv(out/'R7_CORRELATION_SIMULATION.csv',index=False,float_format='%.12g')
    def wilson(k,n,z=1.96):
        p=k/n;d=1+z*z/n;center=(p+z*z/(2*n))/d
        radius=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
        return [float(max(0,center-radius)),float(min(1,center+radius))]
    result={'simulation':'yearwise IID signs, country outcomes perfectly dependent within year',
            'replicates':reps,'groups_per_rep':12,'countries_per_group':200,
            'null':'E[annual mean gain|past years]=0',
            'naive_rowwise':{'alarms':int(df.naive.sum()),'rate':float(df.naive.mean()),'wilson95':wilson(int(df.naive.sum()),reps)},
            'year_grouped':{'alarms':int(df.year_aggregated.sum()),'rate':float(df.year_aggregated.mean()),'wilson95':wilson(int(df.year_aggregated.sum()),reps)},
            'interpretation':'Naive row-by-row betting violates its conditional null due shared year shock; year means obey it here',
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'R7_SIMULATION_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='../results/simulation');p.add_argument('--replicates',type=int,default=1000)
    args=p.parse_args();run(args.out,args.replicates)
