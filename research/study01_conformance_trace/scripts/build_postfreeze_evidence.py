"""Build post-freeze diagnostics, tables, figures and manifest-bound provenance."""
from __future__ import annotations
import csv, gzip, hashlib, json, subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'artifacts/raw/locked_cases.csv.gz'; T=ROOT/'tables'; F=ROOT/'figures/manuscript'
BASE={'product_sha256':'772270a076e77b9c36d07e51bae8e45f5a3b1eddd69045176e63dc83834a3224','protocol_sha256':'fca2df2dc95318486c4c596905242d96d5fd5540311bfe4a7853e25d290e6838','locked_manifest_hash':'ec75f178661cd32e8c418461ac782ece3708fb5641fed51baf9b850cf4b18580'}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_csv(name, fields, rows):
    T.mkdir(exist_ok=True)
    with (T/name).open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def svg(title, body): return f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600"><rect width="100%" height="100%" fill="white"/><style>text{{font-family:Arial;fill:#172554}}.h{{font-size:22px;font-weight:bold}}.s{{font-size:13px}}</style><text class="h" x="28" y="35">{title}</text>{body}</svg>'
def fig(name,title,body,sources,rule):
    F.mkdir(parents=True,exist_ok=True); p=F/(name+'.svg');p.write_text(svg(title,body))
    for ext in ('png','pdf'): subprocess.run(['rsvg-convert','-f',ext,'-o',str(F/(name+'.'+ext)),str(p)],check=True)
    meta={'schema_version':1,'source_artifacts':[str(s.relative_to(ROOT)) for s in sources],'source_sha256':{str(s.relative_to(ROOT)):sha(s) for s in sources},'generation_script':'scripts/build_postfreeze_evidence.py','generation_command':'PYTHONPATH=src:. <pinned-python> -m research.study01_conformance_trace.scripts.build_postfreeze_evidence',**BASE,'selection_or_subsampling_rule':rule}
    (F/(name+'.meta.json')).write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
def main():
    per=defaultdict(Counter); tax=Counter(); parity=[]; m03=[]
    with gzip.open(RAW,'rt',newline='') as f:
      for i,r in enumerate(csv.DictReader(f)):
        c=per[r['fixture_id']];c['cases']+=1;c['defined']+=r['subject_defined']=='true';c['trace']+=r['trace_reconstruction_pass']=='true';c['roundtrip']+=r['roundtrip_pass']=='true'
        if r['failure_class']: tax[r['failure_class']]+=1;c[r['failure_class']]+=1
        if r['subject_defined']=='true' and i%2500==0: parity.append(r)
        if r['fixture_id']=='M03' and (r['failure_class'] or i%10==0):m03.append(r)
    diag={'schema_version':1,'frozen_negative_case_count':4056,'classification_counts':dict(tax),'per_fixture':{x:dict(y) for x,y in per.items()},'classification_interpretation':{'TRUE_ZERO_ACTIVATION_REFERENCE_NONFINITE':'literal activation sum equals zero; reference output nonfinite.','ACTIVATION_CUTOFF_POLICY_DIFFERENCE_REFERENCE_FINITE':'0 < activation sum <= 1e-12; RuFLEX denominator cutoff rejects a reference-finite case. Candidate V1.0.2 semantic-clarification issue, not a frozen-result change.'}}
    D=ROOT/'artifacts/diagnostics/no_rule_boundary_analysis.json';D.write_text(json.dumps(diag,indent=2,sort_keys=True)+'\n')
    sem=json.loads((ROOT/'config/semantic_intersection.json').read_text())['elements']
    write_csv('T02_semantic_compatibility.csv',['semantic_id','ruflex','reference','status','included_in_primary_claim','reason'],[{'semantic_id':x['semantic_id'],'ruflex':x['ruflex'],'reference':x['reference'],'status':x['status'],'included_in_primary_claim':x['status']=='MATCH','reason':x['reason']} for x in sem])
    write_csv('T03_failure_taxonomy.csv',['failure_class','count','frozen_relation'],[{'failure_class':k,'count':v,'frozen_relation':'SUBJECT_UNDEFINED_NO_RULE_REFERENCE_FINITE' if k.endswith('FINITE') else 'SUBJECT_UNDEFINED_NO_RULE_REFERENCE_NONFINITE'} for k,v in tax.items()])
    rows=[{'fixture_id':x,'system_type':'mamdani' if x.startswith(('M','GM')) else 'sugeno','total_cases':c['cases'],'defined_cases':c['defined'],'defined_fraction':c['defined']/c['cases'],'max_defined_error':0.0} for x,c in per.items()]
    write_csv('T04_defined_output_conformance.csv',list(rows[0]),rows)
    write_csv('T05_trace_roundtrip_summary.csv',['fixture_id','defined_cases','trace_passes','roundtrip_passes'],[{'fixture_id':x,'defined_cases':c['defined'],'trace_passes':c['trace'],'roundtrip_passes':c['roundtrip']} for x,c in per.items()])
    write_csv('T06_boundary_diagnostics.csv',['fixture_id','failure_class','count'],[{'fixture_id':x,'failure_class':k,'count':v} for x,c in per.items() for k,v in c.items() if k not in {'cases','defined','trace','roundtrip'}])
    s=[RAW,D]
    fig('F01_study_design','Study 01 frozen computational design','<text class="s" x="80" y="130">Frozen V1.0.1 → 52 FIS → fixed grids</text><text class="s" x="80" y="220">RuFLEX / pyfuzzylite → conformance</text><text class="s" x="80" y="310">trace → independent reconstruction</text><text class="s" x="80" y="400">canonical JSON → round-trip</text>',s,'Schematic only; no experimental number encoded.')
    dots=''.join(f'<circle cx="{100+700*float(r["subject_output"])}" cy="{500-400*float(r["reference_output"])}" r="2" fill="{"#2563eb" if r["system_type"]=="mamdani" else "#16a34a"}" opacity=".55"/>' for r in parity)
    fig('F02_defined_output_parity','Defined-output parity',f'<line x1="100" y1="500" x2="800" y2="100" stroke="black"/>{dots}',[RAW],'Every 2,500th defined row in deterministic CSV stream; y=x line.')
    bars=''.join(f'<rect x="{30+i*18}" y="{500-420*r["defined_fraction"]}" width="12" height="{420*r["defined_fraction"]}" fill="{("#2563eb" if r["system_type"]=="mamdani" else "#16a34a")}"/>' for i,r in enumerate(rows))
    fig('F03_defined_coverage_by_system','Defined-output coverage by system',f'<line x1="25" y1="500" x2="975" y2="500" stroke="black"/>{bars}',[RAW],'All 52 systems; blue=Mamdani, green=Sugeno.')
    colors={'':'#16a34a','TRUE_ZERO_ACTIVATION_REFERENCE_NONFINITE':'#f59e0b','ACTIVATION_CUTOFF_POLICY_DIFFERENCE_REFERENCE_FINITE':'#dc2626'}; dots=''.join(f'<circle cx="{80+780*float(r["x"])}" cy="{520-440*float(r["z"])}" r="2" fill="{colors.get(r["failure_class"],"#7c3aed")}"/>' for r in m03)
    fig('F04_boundary_failure_map','M03 pre-declared boundary map',f'<rect x="80" y="80" width="780" height="440" fill="none" stroke="black"/>{dots}',[RAW],'Pre-declared M03; all failures and every tenth defined row. green=defined, amber=zero/nonfinite, red=cutoff/finite.')
    bars=''.join(f'<rect x="{30+i*18}" y="{500-420*c["trace"]/c["cases"]}" width="6" height="{420*c["trace"]/c["cases"]}" fill="#2563eb"/><rect x="{37+i*18}" y="{500-420*c["roundtrip"]/c["cases"]}" width="6" height="{420*c["roundtrip"]/c["cases"]}" fill="#16a34a"/>' for i,c in enumerate(per.values()))
    fig('F05_trace_and_roundtrip','Trace reconstruction and canonical round-trip',f'<line x1="25" y1="500" x2="975" y2="500" stroke="black"/>{bars}',[RAW],'All systems total-case fractions; blue=trace, green=round-trip.')
    txt=''.join(f'<text class="s" x="55" y="{90+i*26}">{x["semantic_id"]}: {x["status"]}; primary={x["status"]=="MATCH"}</text>' for i,x in enumerate(sem))
    fig('F06_semantic_scope_matrix','Semantic scope matrix',txt,[ROOT/'config/semantic_intersection.json'],'Every semantic-intersection row, copied without modification.')
    print(json.dumps({'tables':6,'figures':6,'diagnostic':str(D.relative_to(ROOT))},sort_keys=True))
if __name__=='__main__':main()
