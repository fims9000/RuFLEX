from __future__ import annotations

from pathlib import Path

import pandas as pd

from ruflex.application.datasets import build_dataset_contract, inspect_dataset, persist_dataset_bytes, persist_dataset_contract, run_data_audit
from ruflex.application.behavior import create_behavior_spec, run_behavior_spec
from ruflex.application.fis import create_default_fis
from ruflex.application.lineage import build_project_lineage
from ruflex.application.projects import ProjectService
from ruflex.application.training import create_validation_evaluation, evaluate_final_test, select_validation_threshold, train_decision_tree


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "lineage-project"
    ProjectService().create(root, name="Lineage")
    frame = pd.DataFrame({
        "entity_id": [f"e{i}" for i in range(30)],
        "temperature": [float(i) for i in range(30)],
        "pressure": [float((i * 7) % 11) for i in range(30)],
        "target": [0 if i < 15 else 1 for i in range(30)],
    })
    payload = frame.to_csv(index=False).encode()
    ref = persist_dataset_bytes(root, payload, original_name="lineage.csv")
    profile = inspect_dataset(frame, source_artifact_sha256=ref.sha256)
    contract = build_dataset_contract(profile, target="target", task="binary_classification", id_columns=["entity_id"])
    persist_dataset_contract(root, contract, run_data_audit(contract, frame), profile)
    return root


def test_lineage_uses_persisted_dataset_run_and_evaluation_references(tmp_path: Path) -> None:
    root = _project(tmp_path)
    run = train_decision_tree(root, seed=9)
    evaluation = create_validation_evaluation(root, run.run_id)
    threshold = select_validation_threshold(root, evaluation.evaluation_id)
    final_test = evaluate_final_test(root, evaluation.evaluation_id, threshold_id=threshold.threshold_id)

    graph = build_project_lineage(root)
    ids = {node.id for node in graph.nodes}
    assert f"run:{run.run_id}" in ids
    assert f"evaluation:{evaluation.evaluation_id}" in ids
    assert f"final-test:{final_test.final_test_id}" in ids
    dataset = next(node for node in graph.nodes if node.kind == "dataset")
    assert any(edge.source == dataset.id and edge.target == f"run:{run.run_id}" and edge.relation == "trained_on" for edge in graph.edges)
    assert any(edge.source == f"run:{run.run_id}" and edge.target == f"evaluation:{evaluation.evaluation_id}" and edge.relation == "evaluated_as" for edge in graph.edges)
    assert any(edge.target == f"final-test:{final_test.final_test_id}" and edge.relation == "applied_threshold" for edge in graph.edges)
    assert any(edge.source == f"evaluation:{evaluation.evaluation_id}" and edge.target == f"final-test:{final_test.final_test_id}" and edge.relation == "opened_after_validation_freeze" for edge in graph.edges)
    assert graph.scientific_note.startswith("Project Lineage is reconstructed")


def test_lineage_links_exact_fis_revision_to_behavior_spec_and_result_after_reopen(tmp_path: Path) -> None:
    root = _project(tmp_path)
    fis = create_default_fis(root, name="FIS behavior lineage")
    sample = {variable.name: (variable.minimum + variable.maximum) / 2 for variable in fis.inputs}
    spec = create_behavior_spec(root, {
        "fis_id": str(fis.fis_id),
        "fis_semantic_hash": fis.semantic_hash,
        "name": "FIS midpoint range",
        "kind": "output_range",
        "sample": sample,
        "minimum": 0.0,
        "maximum": 1.0,
        "rationale": "FIS semantic revision is the exact bound object.",
    })
    result = run_behavior_spec(root, spec.spec_id)
    ProjectService().open(root, read_only=True)
    graph = build_project_lineage(root)
    fis_node = f"fis-revision:{fis.fis_id}:{fis.semantic_hash}"
    spec_node = f"behavior-spec:{spec.spec_id}"
    result_node = f"behavior-result:{result.result_id}"
    assert {fis_node, spec_node, result_node} <= {node.id for node in graph.nodes}
    assert any(edge.source == fis_node and edge.target == spec_node and edge.relation == "specified_for" for edge in graph.edges)
    assert any(edge.source == spec_node and edge.target == result_node and edge.relation == "executed_as" for edge in graph.edges)
