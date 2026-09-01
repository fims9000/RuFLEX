"""Post-execution result freeze derived only from immutable locked raw rows."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'artifacts/raw/locked_outcomes.jsonl'
OUT=ROOT/'artifacts/result_freeze'
FAMILIES=('V01','V06','V07')

def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(): return [json.loads(line) for line in RAW.read_text().splitlines() if line]
def write_csv(name:str, items:list[dict]):
 path=OUT/'tables'/name; path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=list(items[0]) if items else ['status']); writer.writeheader(); writer.writerows(items)
 return path
def svg(name:str,title:str,lines:list[str]):
 path=OUT/'figures'/name; path.parent.mkdir(parents=True,exist_ok=True); height=70+28*len(lines)
 body=''.join(f'<text x="24" y="{60+28*i}" font-size="16">{line}</text>' for i,line in enumerate(lines))
 path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}"><rect width="100%" height="100%" fill="#ffffff"/><text x="24" y="32" font-size="22" font-weight="bold">{title}</text>{body}</svg>\n')
 return path
def main():
 r=rows(); manifest=json.loads((ROOT/'config/locked_suite_manifest.json').read_text()); plan=[json.loads(x) for x in (ROOT/'artifacts/manifests/locked_execution_plan.jsonl').read_text().splitlines()]
 assert len(r)==120 and len({x['scenario_id'] for x in r})==120 and len(plan)==60
 assert all(x['product_sha']==manifest['product_sha256'] and x['protocol_sha']==manifest['protocol_hash'] and x['manifest_id']==manifest['manifest_hash'] for x in r)
 family=[]
 for f in FAMILIES:
  rr=[x for x in r if x['family']==f]; clean=[x for x in rr if x['clean_or_corrupt']=='clean']; corrupt=[x for x in rr if x['clean_or_corrupt']=='corrupt']
  family.append({'family':f,'pairs':len(rr)//2,'clean':len(clean),'corrupt':len(corrupt),'prevented':sum(x['product_outcome'].startswith('PREVENTED') for x in corrupt),'missed':sum(x['product_outcome']=='MISSED' for x in corrupt),'false_blocks':sum(x['false_block'] for x in clean),'false_warnings':sum(x['false_warning'] for x in clean)})
 summary={'study':'Study 02 — Protocol Integrity','product_sha':manifest['product_sha256'],'protocol_sha':manifest['protocol_hash'],'manifest_id':manifest['manifest_hash'],'execution_plan_sha':manifest['locked_execution_plan_sha256'],'raw_sha256':sha(RAW),'locked_pairs':60,'total_executions':120,'distinct_base_inputs':len({x['base_input_hash'] for x in r}),'families':family,'total_corrupt':60,'total_prevented':sum(x['prevented'] for x in family),'total_missed':sum(x['missed'] for x in family),'total_clean':60,'clean_false_blocks':sum(x['false_blocks'] for x in family),'clean_false_warnings':sum(x['false_warnings'] for x in family),'baseline':{'clean_alerts':sum(x['baseline_outcome']=='ALERT' for x in r if x['clean_or_corrupt']=='clean'),'corrupt_alerts':sum(x['baseline_outcome']=='ALERT' for x in r if x['clean_or_corrupt']=='corrupt')},'persistence':Counter(f"{x['save_status']}/{x['reopen_status']}" for x in r),'failure_taxonomy':Counter(x['failure_class'] or 'NONE' for x in r)}
 summary['persistence']=dict(summary['persistence']); summary['failure_taxonomy']=dict(summary['failure_taxonomy'])
 write_csv('T01_locked_scenario_summary.csv',family)
 write_csv('T02_prevention_by_family.csv',[{k:v for k,v in x.items() if k in ('family','corrupt','prevented','missed')} for x in family])
 write_csv('T03_clean_control_results.csv',[{k:v for k,v in x.items() if k in ('family','clean','false_blocks','false_warnings')} for x in family])
 write_csv('T04_ruflex_vs_basic_manifest_audit.csv',[{'population':'corrupt','ruflex_prevented':summary['total_prevented'],'basic_manifest_alerts':summary['baseline']['corrupt_alerts']},{'population':'clean','ruflex_prevented':0,'basic_manifest_alerts':summary['baseline']['clean_alerts']}])
 write_csv('T05_persistence_reopen.csv',[{'status':k,'count':v} for k,v in summary['persistence'].items()])
 write_csv('T06_failure_taxonomy.csv',[{'failure_class':k,'count':v} for k,v in summary['failure_taxonomy'].items()])
 figures=[svg('F01_study_design.svg','F01 Study design',['60 matched pairs','120 scenario executions','V01 / V06 / V07']),svg('F02_prevention_by_family.svg','F02 Prevention by family',[f"{x['family']}: {x['prevented']}/{x['corrupt']} prevented" for x in family]),svg('F03_clean_control_specificity.svg','F03 Clean controls',[f"False blocks {summary['clean_false_blocks']}",f"False warnings {summary['clean_false_warnings']} "]),svg('F04_ruflex_vs_baseline.svg','F04 RuFLEX vs BASIC_MANIFEST_AUDIT',[f"RuFLEX prevention {summary['total_prevented']}/60",f"Baseline corrupt alerts {summary['baseline']['corrupt_alerts']}/60"]),svg('F05_persistence_lifecycle.svg','F05 Persistence lifecycle',[f"{k}: {v}" for k,v in summary['persistence'].items()]),svg('F06_negative_failure_evidence.svg','F06 Negative/failure evidence',[f"{k}: {v}" for k,v in summary['failure_taxonomy'].items()])]
 provenance={'schema_version':1,'source_raw_sha256':summary['raw_sha256'],'source_execution_plan_sha256':summary['execution_plan_sha'],'figures':[{'id':p.stem.split('_')[0],'path':str(p.relative_to(ROOT)),'derived_from':'locked_outcomes.jsonl'} for p in figures]}
 (OUT/'FIGURE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
 (OUT/'THESIS_NUMBERS.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 (OUT/'THESIS_EVIDENCE.md').write_text(f"# Study 02 evidence\n\nAll numbers are derived from `{RAW.name}` SHA-256 `{summary['raw_sha256']}`.\n\nPrevention: {summary['total_prevented']}/{summary['total_corrupt']}; clean false blocks/warnings: {summary['clean_false_blocks']}/{summary['clean_false_warnings']}.\n")
 (OUT/'STUDY02_RESULTS.md').write_text(f"# Study 02 results\n\nAll 120 locked executions completed. Prevention was {summary['total_prevented']}/60; misses were {summary['total_missed']}.\n")
 (OUT/'STUDY02_LIMITATIONS.md').write_text('# Limitations\n\nThis controlled study supports prevention claims for V01, V06 and V07 through the specified Product V1.0.1 canonical services. It does not establish retrospective detection or support claims for unsupported/partial violation families.\n')
 (OUT/'STUDY02_RECEIPT.md').write_text(f"# Result-freeze receipt\n\nRaw artifact: `{RAW}`\n\nSHA-256: `{summary['raw_sha256']}`\n\nFrozen manifest: `{summary['manifest_id']}`\n")
 (OUT/'FINAL_VALIDATOR.json').write_text(json.dumps({'status':'PASS','raw_rows':len(r),'unique_scenarios':len({x['scenario_id'] for x in r}),'unique_base_inputs':summary['distinct_base_inputs'],'pairs_by_family':{f:sum(x['family']==f for x in plan) for f in FAMILIES},'raw_sha256':summary['raw_sha256'],'frozen_identities_match':True,'figure_provenance_complete':len(figures)==6},indent=2,sort_keys=True)+'\n')
 print(json.dumps(summary,sort_keys=True))
if __name__=='__main__': main()
