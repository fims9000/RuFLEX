from __future__ import annotations
import hashlib,json
from pathlib import Path
from research.study02_protocol_integrity.scripts.freeze_protocol import main as freeze
from research.study02_protocol_integrity.scripts.locked_executor import validate_plan
ROOT=Path(__file__).resolve().parents[1]
def main():
 manifest=json.loads((ROOT/'config/locked_suite_manifest.json').read_text()); before=manifest['manifest_hash']; freeze(); after=json.loads((ROOT/'config/locked_suite_manifest.json').read_text())
 assert before==after['manifest_hash'] and after['authorization_is_external_to_manifest'] is True
 assert hashlib.sha256((ROOT.parents[1]/'release/RuFLEX_PRODUCT_V1_0_1_SOURCE.zip').read_bytes()).hexdigest()==after['product_sha256']
 rows=[json.loads(x) for x in (ROOT/'oracle/scenario_ground_truth.jsonl').read_text().splitlines()]
 assert len(rows)==18 and len({x['scenario_id'] for x in rows})==18
 plan=validate_plan(); assert plan['status']=='PASS' and plan['executor_locked'] is True
 historical=json.loads((ROOT/'artifacts/aggregated/dev_report.json').read_text())
 assert historical['status']=='SUPERSEDED_HARNESS_ONLY'
 native=json.loads((ROOT/'artifacts/aggregated/dev_native_report.json').read_text())
 assert native['status']=='PRODUCT_BACKED_DEV' and native['rows']==18
 print('STUDY02_PRE_FREEZE_VALIDATOR_PASS')
if __name__=='__main__':main()
