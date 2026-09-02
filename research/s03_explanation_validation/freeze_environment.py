"""Record the exact pre-benchmark Python research environment."""
from __future__ import annotations
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent; CONFIG=ROOT/"config"
def version(name: str) -> str:
    try:return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:return "NOT_INSTALLED"
def main() -> dict:
    result={"schema_version":1,"purpose":"S03 Phase 0.2 pre-benchmark environment lock","python":sys.version,"platform":platform.platform(),"packages":{name:version(name) for name in ("numpy","pandas","scikit-learn","shap","torch","quantus","scipy")},"benchmark_results_seen":False,"benchmark_explanations_generated":False,"scientific_outcomes_seen":False}
    (CONFIG/"environment_lock.json").write_text(json.dumps(result,sort_keys=True,separators=(",",":"))+"\n")
    return result
if __name__=="__main__": print(json.dumps(main(),sort_keys=True))
