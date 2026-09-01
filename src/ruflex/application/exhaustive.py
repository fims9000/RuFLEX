from __future__ import annotations
import itertools, json
from pathlib import Path
from uuid import UUID
from ruflex.application.evidence import _artifact_payload, _atomic_write_text
from ruflex.application.fis import FISError, evaluate_fis, load_fis
from ruflex.application.training import load_training_run
from ruflex.domain.exhaustive import ExhaustiveLabResult

class ExhaustiveLabError(ValueError): pass
def _root(root:Path)->Path:
    path=Path(root).resolve()/"evidence"/"exhaustive-lab"; path.mkdir(parents=True,exist_ok=True); return path
def run_tree_exhaustive(root:Path, run_id:UUID)->ExhaustiveLabResult:
    run=load_training_run(root,run_id)
    if run.model_kind!="decision_tree": raise ExhaustiveLabError("Exact finite path enumeration is available only for a persisted Decision Tree.")
    tree=_artifact_payload(root,run.model_artifact_sha256)["tree"]
    paths=[]
    def walk(node:int, constraints:list[str]):
        if tree["children_left"][node]==-1: paths.append({"leaf_id":node,"constraints":constraints,"value":tree["values"][node]}); return
        feature=run.feature_columns[tree["feature_index"][node]]; threshold=float(tree["threshold"][node]); walk(tree["children_left"][node],constraints+[f"{feature} ≤ {threshold:.8g}"]); walk(tree["children_right"][node],constraints+[f"{feature} > {threshold:.8g}"])
    walk(0,[])
    result=ExhaustiveLabResult(kind="decision_tree_structure",exactness_label="EXACT_FINITE_STRUCTURE",run_id=run_id,state_count=len(paths),state_estimate=len(paths),max_states=len(paths),paths=paths,scientific_note="Every leaf path of this persisted finite Decision Tree is enumerated exactly. This does not claim exhaustive explanation of an ensemble or continuous model.")
    _atomic_write_text(_root(root)/f"{result.result_id}.json",result.model_dump_json(indent=2)); _atomic_write_text(_root(root)/"active-result.json",json.dumps({"result_id":str(result.result_id)})); return result
def estimate_fis_grid_states(root:Path, points:int=3)->int:
    spec=load_fis(root)
    if points<2 or points>9: raise ExhaustiveLabError("Grid points per input must be 2 through 9.")
    return points ** len(spec.inputs)
def run_fis_grid_exhaustive(root:Path, points:int=3, max_states:int=10000)->ExhaustiveLabResult:
    spec=load_fis(root)
    estimate=estimate_fis_grid_states(root,points)
    if estimate>max_states: raise ExhaustiveLabError(f"Declared grid would evaluate {estimate} states, exceeding strict max_states={max_states}. Reduce grid points or increase the explicit limit after review.")
    grid={v.name:[float(v.minimum+(v.maximum-v.minimum)*i/(points-1)) for i in range(points)] for v in spec.inputs}
    states=[]; uncovered=[]; conflicts=[]; hits={rule.rule_id:0 for rule in spec.rules}
    for values in itertools.product(*grid.values()):
        sample=dict(zip(grid,values,strict=True))
        try:
            evaluation=evaluate_fis(spec,sample); active=[item.rule_id for item in evaluation.trace.rules if item.firing_strength>1e-9]
            states.append({"inputs":sample,"output":evaluation.output,"active_rules":active})
            if not active: uncovered.append({"inputs":sample,"reason":"no rule fires on declared discrete grid state"})
            if len(active)>1: conflicts.append({"inputs":sample,"active_rules":active,"note":"Multiple rules fire on this declared grid state; this is overlap evidence, not necessarily a defect."})
        except FISError as error:
            active=[]; states.append({"inputs":sample,"output":None,"active_rules":active,"undefined":str(error)}); uncovered.append({"inputs":sample,"reason":str(error)})
        for item in active: hits[item]+=1
    result=ExhaustiveLabResult(kind="fis_discrete_grid",exactness_label="EXACT_ON_DECLARED_DISCRETE_GRID",fis_semantic_hash=spec.semantic_hash,declared_grid=grid,state_count=len(states),state_estimate=estimate,max_states=max_states,paths=states,uncovered_states=uncovered,dead_rules=[str(key) for key,value in hits.items() if value==0],conflict_states=conflicts,scientific_note="Each declared finite grid state is evaluated by the canonical FIS exactly. Dead rules are dead ON THE DECLARED GRID only; overlap/conflict evidence is reported separately. The grid is representative and does not fully explain the continuous FIS domain.")
    _atomic_write_text(_root(root)/f"{result.result_id}.json",result.model_dump_json(indent=2)); _atomic_write_text(_root(root)/"active-result.json",json.dumps({"result_id":str(result.result_id)})); return result
def load_latest_exhaustive(root:Path)->ExhaustiveLabResult:
    pointer=json.loads((_root(root)/"active-result.json").read_text()); return ExhaustiveLabResult.model_validate_json((_root(root)/f"{pointer['result_id']}.json").read_text())
