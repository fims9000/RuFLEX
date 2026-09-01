from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ruflex.application.datasets import DatasetContract, load_dataset_contract, load_dataset_profile
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract
from ruflex.domain.fis import FISSpec
from ruflex.domain.expert_correction import ExpertCorrectionRevision
from ruflex.domain.lineage import LineageEdge, LineageGraph, LineageNode
from ruflex.domain.training import (
    AnalysisComparison,
    AnalysisEvaluation,
    CalibrationTransform,
    DecisionThresholdPolicy,
    FinalTestEvaluation,
    TrainingRun,
    TrainingStudy,
    TreePathEvidence,
)
from ruflex.application.generalization import GeneralizationContract, SliceAnalysis
from ruflex.domain.assurance import AssuranceCase
from ruflex.domain.behavior import BehaviorSpec, BehaviorSpecResult
from ruflex.domain.evidence import ExplanationReproducibilityAnalysis
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.verification import VerificationBundle


def _json_models(root: Path, model: type[BaseModel], *, exclude: Iterable[str] = ()) -> list[BaseModel]:
    """Load UUID-named JSON objects from a directory without following pointers.

    A malformed optional historical object is omitted from lineage rather than
    making a project impossible to open. The object itself remains untouched.
    """
    if not root.is_dir():
        return []
    excluded = set(exclude)
    items: list[BaseModel] = []
    for path in sorted(root.glob("*.json")):
        if path.name in excluded:
            continue
        try:
            UUID(path.stem)
        except ValueError:
            continue
        try:
            items.append(model.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError, ValueError):
            continue
    return items


def _node_id(kind: str, object_id: object) -> str:
    return f"{kind}:{object_id}"


def build_project_lineage(project_root: Path) -> LineageGraph:
    """Build a read-only lineage graph from explicit persisted references only."""
    root = Path(project_root).resolve()
    nodes: dict[str, LineageNode] = {}
    edges: dict[tuple[str, str, str], LineageEdge] = {}

    def add_node(node: LineageNode) -> str:
        nodes[node.id] = node
        return node.id

    def add_edge(source: str | None, target: str | None, relation: str) -> None:
        if not source or not target or source == target:
            return
        if source not in nodes or target not in nodes:
            return
        edges[(source, target, relation)] = LineageEdge(source=source, target=target, relation=relation)

    dataset_node: str | None = None
    try:
        contract: DatasetContract = load_dataset_contract(root)
        try:
            profile = load_dataset_profile(root)
            detail = f"{profile.row_count} rows · {contract.task} · target {contract.target}"
        except (OSError, ValueError, ValidationError):
            detail = f"{contract.task} · target {contract.target}"
        dataset_node = add_node(LineageNode(
            id=_node_id("dataset", contract.dataset_fingerprint),
            kind="dataset",
            label=f"Dataset · {contract.target}",
            detail=detail,
            target="DATA",
            object_id=contract.dataset_fingerprint,
        ))
    except (OSError, ValueError, ValidationError):
        contract = None  # type: ignore[assignment]

    # FIS revisions are true semantic revisions. We show them as a chain, but
    # do not invent a dataset -> FIS edge because imported FIS files may be
    # independent of the active dataset.
    fis_root = root / "models" / "fis"
    fis_revision_nodes: dict[str, str] = {}
    revision_root = fis_root / "revisions"
    if revision_root.is_dir():
        for fis_dir in sorted(path for path in revision_root.iterdir() if path.is_dir()):
            previous: str | None = None
            for ordinal, path in enumerate(sorted(fis_dir.glob("*.json")), start=1):
                try:
                    spec = FISSpec.model_validate_json(path.read_text(encoding="utf-8"))
                except (OSError, ValidationError, ValueError):
                    continue
                semantic = spec.semantic_hash or path.stem
                node = add_node(LineageNode(
                    id=_node_id("fis-revision", f"{spec.fis_id}:{semantic}"),
                    kind="fis_revision",
                    label=f"{spec.name} · revision {ordinal}",
                    detail=f"{spec.system_type} · {semantic[:12]}",
                    target="MODELS",
                    object_id=str(spec.fis_id),
                ))
                fis_revision_nodes[semantic] = node
                add_edge(previous, node, "revised_to")
                previous = node
    else:
        for path in sorted(fis_root.glob("*.json")) if fis_root.is_dir() else []:
            try:
                spec = FISSpec.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError):
                continue
            add_node(LineageNode(
                id=_node_id("fis", spec.fis_id), kind="fis", label=spec.name,
                detail=spec.system_type, target="MODELS", object_id=str(spec.fis_id),
            ))

    runs = [item for item in _json_models(root / "runs", TrainingRun, exclude=("active-training-run.json",)) if isinstance(item, TrainingRun)]
    run_nodes: dict[UUID, str] = {}
    for run in runs:
        node = add_node(LineageNode(
            id=_node_id("run", run.run_id),
            kind="training_run",
            label=f"{run.model_kind} · seed {run.seed}",
            detail=f"validation · {run.run_id.hex[:8]}",
            target="STUDIES",
            object_id=str(run.run_id),
            status=run.status,
        ))
        run_nodes[run.run_id] = node
        if dataset_node and run.dataset_fingerprint and contract is not None and run.dataset_fingerprint == contract.dataset_fingerprint:
            add_edge(dataset_node, node, "trained_on")

    studies = [item for item in _json_models(root / "studies", TrainingStudy, exclude=("active-study.json",)) if isinstance(item, TrainingStudy)]
    study_nodes: dict[UUID, str] = {}
    for study in studies:
        study_node = add_node(LineageNode(
            id=_node_id("study", study.study_id), kind="study", label=study.name,
            detail=f"{len(study.seed_runs)} seeds · select {study.selection_metric}", target="STUDIES",
            object_id=str(study.study_id), status="selected",
        ))
        study_nodes[study.study_id] = study_node
        for embedded in study.seed_runs:
            run_node = run_nodes.get(embedded.run_id)
            add_edge(study_node, run_node, "contains_seed_run")
            if embedded.run_id == study.selected_run_id:
                add_edge(study_node, run_node, "selected_run")

    evaluations = [item for item in _json_models(root / "analyses" / "evaluations", AnalysisEvaluation, exclude=("active-evaluation.json",)) if isinstance(item, AnalysisEvaluation)]
    evaluation_nodes: dict[UUID, str] = {}
    for evaluation in evaluations:
        node = add_node(LineageNode(
            id=_node_id("evaluation", evaluation.evaluation_id), kind="evaluation",
            label=f"Validation evaluation · {evaluation.model_kind or 'model'}",
            detail=f"{len(evaluation.metrics)} metrics · test locked", target="ANALYSES",
            object_id=str(evaluation.evaluation_id), status=evaluation.test_status,
        ))
        evaluation_nodes[evaluation.evaluation_id] = node
        add_edge(run_nodes.get(evaluation.run_id), node, "evaluated_as")
        if dataset_node and contract is not None and evaluation.dataset_fingerprint == contract.dataset_fingerprint:
            add_edge(dataset_node, node, "validation_evidence_from")

    calibrations = [item for item in _json_models(root / "analyses" / "calibrations", CalibrationTransform, exclude=("active-calibration.json",)) if isinstance(item, CalibrationTransform)]
    calibration_nodes: dict[UUID, str] = {}
    for calibration in calibrations:
        node = add_node(LineageNode(
            id=_node_id("calibration", calibration.calibration_id), kind="calibration",
            label="Platt calibration", detail=f"validation · n={calibration.fit_sample_count}",
            target="ANALYSES", object_id=str(calibration.calibration_id), status=calibration.test_status,
        ))
        calibration_nodes[calibration.calibration_id] = node
        add_edge(evaluation_nodes.get(calibration.evaluation_id), node, "calibrated_by")
        add_edge(run_nodes.get(calibration.run_id), node, "calibrates_run")

    thresholds = [item for item in _json_models(root / "analyses" / "thresholds", DecisionThresholdPolicy, exclude=("active-threshold.json",)) if isinstance(item, DecisionThresholdPolicy)]
    threshold_nodes: dict[UUID, str] = {}
    for threshold in thresholds:
        node = add_node(LineageNode(
            id=_node_id("threshold", threshold.threshold_id), kind="decision_threshold",
            label=f"Decision threshold · {threshold.selected_threshold:.2f}",
            detail=f"{threshold.objective} · {threshold.probability_source} probability", target="ANALYSES",
            object_id=str(threshold.threshold_id), status=threshold.test_status,
        ))
        threshold_nodes[threshold.threshold_id] = node
        add_edge(evaluation_nodes.get(threshold.evaluation_id), node, "threshold_selected_from")
        if threshold.calibration_id is not None:
            add_edge(calibration_nodes.get(threshold.calibration_id), node, "uses_calibration")

    final_tests = [item for item in _json_models(root / "analyses" / "final-tests", FinalTestEvaluation, exclude=("active-final-test.json",)) if isinstance(item, FinalTestEvaluation)]
    for final_test in final_tests:
        node = add_node(LineageNode(
            id=_node_id("final-test", final_test.final_test_id), kind="final_test_evaluation",
            label=f"Final-test evaluation · {final_test.model_kind}",
            detail=f"{final_test.test_row_count} rows · frozen policy", target="ANALYSES",
            object_id=str(final_test.final_test_id), status=final_test.status,
        ))
        add_edge(run_nodes.get(final_test.run_id), node, "final_test_evaluated_as")
        add_edge(evaluation_nodes.get(final_test.evaluation_id), node, "opened_after_validation_freeze")
        if final_test.calibration_id is not None:
            add_edge(calibration_nodes.get(final_test.calibration_id), node, "applied_calibration")
        if final_test.threshold_id is not None:
            add_edge(threshold_nodes.get(final_test.threshold_id), node, "applied_threshold")
        if dataset_node and contract is not None and final_test.dataset_fingerprint == contract.dataset_fingerprint:
            add_edge(dataset_node, node, "final_test_evidence_from")

    comparisons = [item for item in _json_models(root / "analyses" / "comparisons", AnalysisComparison, exclude=("active-comparison.json",)) if isinstance(item, AnalysisComparison)]
    for comparison in comparisons:
        subject_count = len(comparison.run_ids) + int(comparison.fis_id is not None)
        alignment = comparison.validation_alignment.replace("_", " ")
        node = add_node(LineageNode(
            id=_node_id("comparison", comparison.comparison_id), kind="comparison",
            label="Validation comparison", detail=f"{subject_count} subjects · {alignment} · test locked",
            target="ANALYSES", object_id=str(comparison.comparison_id), status="validation_only",
        ))
        for run_id in comparison.run_ids:
            add_edge(run_nodes.get(run_id), node, "compared_in")
        if comparison.fis_semantic_hash is not None:
            add_edge(fis_revision_nodes.get(comparison.fis_semantic_hash), node, "compared_in")

    slices = [item for item in _json_models(root / "analyses" / "slices", SliceAnalysis, exclude=("active-slice-analysis.json",)) if isinstance(item, SliceAnalysis)]
    slice_nodes: dict[UUID, str] = {}
    for analysis in slices:
        node = add_node(LineageNode(
            id=_node_id("slice", analysis.analysis_id), kind="slice_analysis",
            label=f"Slice analysis · {analysis.metric}", detail=f"{len(analysis.results)} slices · validation",
            target="ANALYSES", object_id=str(analysis.analysis_id), status=analysis.test_status,
        ))
        slice_nodes[analysis.analysis_id] = node
        add_edge(evaluation_nodes.get(analysis.evaluation_id), node, "sliced_as")

    tree_paths = [item for item in _json_models(root / "evidence" / "tree-paths", TreePathEvidence, exclude=("latest.json",)) if isinstance(item, TreePathEvidence)]
    for evidence in tree_paths:
        node = add_node(LineageNode(
            id=_node_id("tree-path", evidence.evidence_id), kind="tree_path",
            label="Exact tree execution path", detail=f"leaf {evidence.leaf_id}",
            target="EVIDENCE", object_id=str(evidence.evidence_id), status="EXACT",
        ))
        add_edge(run_nodes.get(evidence.run_id), node, "executed_as")

    explanations = [item for item in _json_models(root / "evidence" / "explanations", ExplanationContract, exclude=("active-explanation.json",)) if isinstance(item, ExplanationContract)]
    explanation_nodes: dict[UUID, str] = {}
    for explanation in explanations:
        node = add_node(LineageNode(
            id=_node_id("explanation", explanation.explanation_id), kind="explanation",
            label=f"{explanation.family} explanation", detail=explanation.epistemic_category,
            target="EVIDENCE", object_id=str(explanation.explanation_id), status=explanation.exactness,
        ))
        explanation_nodes[explanation.explanation_id] = node
        add_edge(run_nodes.get(explanation.run_id), node, "explained_by")

    checks = [item for item in _json_models(root / "evidence" / "explanation-checks", ExplanationCheck, exclude=("active-check.json",)) if isinstance(item, ExplanationCheck)]
    for check in checks:
        node = add_node(LineageNode(
            id=_node_id("explanation-check", check.check_id), kind="explanation_check",
            label="Explanation checks", detail=f"{len(check.checks)} checks", target="EVIDENCE",
            object_id=str(check.check_id), status=check.status,
        ))
        add_edge(explanation_nodes.get(check.explanation_id), node, "validated_by")

    corrections = [
        item for item in _json_models(
            root / "analyses" / "expert-corrections",
            ExpertCorrectionRevision,
            exclude=("active-correction.json",),
        )
        if isinstance(item, ExpertCorrectionRevision)
    ]
    for correction in corrections:
        node = add_node(LineageNode(
            id=_node_id("expert-correction", correction.correction_id),
            kind="expert_correction",
            label="Expert Sugeno correction",
            detail=f"TRAIN only · {len(correction.fitted_rule_ids)} consequents fitted",
            target="MODELS",
            object_id=str(correction.correction_id),
            status=correction.test_status,
        ))
        add_edge(fis_revision_nodes.get(correction.source_semantic_hash), node, "expert_corrected_by")
        add_edge(node, fis_revision_nodes.get(correction.result_semantic_hash), "produced_revision")
        if correction.source_explanation_id is not None:
            add_edge(explanation_nodes.get(correction.source_explanation_id), node, "motivated_correction")

    contracts = [item for item in _json_models(root / "objects" / "protocols" / "generalization", GeneralizationContract) if isinstance(item, GeneralizationContract)]
    generalization_nodes: dict[UUID, str] = {}
    for generalization in contracts:
        node = add_node(LineageNode(
            id=_node_id("generalization", generalization.contract_id), kind="generalization_contract",
            label="Generalization contract", detail=generalization.intended_use, target="ANALYSES",
            object_id=str(generalization.contract_id), status="FROZEN" if generalization.frozen_at else "DRAFT",
        ))
        generalization_nodes[generalization.contract_id] = node
        if dataset_node:
            add_edge(dataset_node, node, "scoped_by")

    for analysis in slices:
        if analysis.generalization_contract_id is not None:
            add_edge(
                generalization_nodes.get(analysis.generalization_contract_id),
                slice_nodes.get(analysis.analysis_id),
                "scopes_slice_analysis",
            )

    policies = [item for item in _json_models(root / "analyses" / "selective-policies", SelectivePredictionPolicy, exclude=("active-policy.json",)) if isinstance(item, SelectivePredictionPolicy)]
    for policy in policies:
        node = add_node(LineageNode(id=_node_id("selective-policy", policy.policy_id), kind="selective_policy", label=f"Selective review · {policy.confidence_cutoff:.2f}", detail="validation-derived ACCEPT/REVIEW policy", target="ANALYSES", object_id=str(policy.policy_id), status=policy.test_status))
        add_edge(evaluation_nodes.get(policy.evaluation_id), node, "review_policy_selected_from")
        add_edge(threshold_nodes.get(policy.class_threshold_id), node, "uses_class_threshold")
        if policy.calibration_id is not None: add_edge(calibration_nodes.get(policy.calibration_id), node, "uses_calibration")

    repro = [item for item in _json_models(root / "evidence" / "explanation-reproducibility", ExplanationReproducibilityAnalysis, exclude=("active-analysis.json",)) if isinstance(item, ExplanationReproducibilityAnalysis)]
    for item in repro:
        node = add_node(LineageNode(id=_node_id("explanation-reproducibility", item.analysis_id), kind="explanation_reproducibility", label="Cross-run explanation reproducibility", detail=f"{len(item.run_ids)} runs · {len(item.validation_case_identities)} cases", target="EVIDENCE", object_id=str(item.analysis_id), status="VALIDATION_ONLY"))
        for run_id in item.run_ids: add_edge(run_nodes.get(run_id), node, "compared_for_explanation_reproducibility")
        for explanation_id in item.explanation_ids: add_edge(explanation_nodes.get(explanation_id), node, "reproducibility_evidence_for")

    behavior_root = root / "evidence" / "behavior-specs"
    behavior_specs = [item for item in _json_models(behavior_root, BehaviorSpec, exclude=("active-spec.json", "active-result.json")) if isinstance(item, BehaviorSpec)]
    behavior_nodes: dict[UUID, str] = {}
    for spec in behavior_specs:
        node = add_node(LineageNode(id=_node_id("behavior-spec", spec.spec_id), kind="behavior_spec", label=spec.name, detail=spec.kind, target="EVIDENCE", object_id=str(spec.spec_id), status="DECLARED"))
        behavior_nodes[spec.spec_id] = node
        if spec.run_id is not None:
            add_edge(run_nodes.get(spec.run_id), node, "specified_for")
        elif spec.fis_semantic_hash is not None:
            add_edge(fis_revision_nodes.get(spec.fis_semantic_hash), node, "specified_for")
    behavior_results: list[BehaviorSpecResult] = []
    if behavior_root.is_dir():
        for path in sorted(behavior_root.glob("result-*.json")):
            try:
                behavior_results.append(BehaviorSpecResult.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValidationError, ValueError):
                continue
    for result in behavior_results:
        node = add_node(LineageNode(id=_node_id("behavior-result", result.result_id), kind="behavior_spec_result", label=f"BehaviorSpec {result.status}", detail=result.detail, target="EVIDENCE", object_id=str(result.result_id), status=result.status))
        add_edge(behavior_nodes.get(result.spec_id), node, "executed_as")

    exhaustive = [item for item in _json_models(root / "evidence" / "exhaustive-lab", ExhaustiveLabResult, exclude=("active-result.json",)) if isinstance(item, ExhaustiveLabResult)]
    for item in exhaustive:
        node = add_node(LineageNode(id=_node_id("exhaustive-lab", item.result_id), kind="exhaustive_lab", label=item.exactness_label.replace("_", " "), detail=f"{item.state_count} declared states", target="EVIDENCE", object_id=str(item.result_id), status=item.exactness_label))
        add_edge(run_nodes.get(item.run_id), node, "exhaustively_inspected")
        if item.fis_semantic_hash is not None: add_edge(fis_revision_nodes.get(item.fis_semantic_hash), node, "exhaustively_inspected")

    assurance_cases = [item for item in _json_models(root / "evidence" / "assurance", AssuranceCase, exclude=("active-case.json",)) if isinstance(item, AssuranceCase)]
    for item in assurance_cases:
        node = add_node(LineageNode(id=_node_id("assurance", item.assurance_id), kind="assurance_case", label="AssuranceCase", detail=f"{len(item.gates)} independent gates", target="EVIDENCE", object_id=str(item.assurance_id), status="EVIDENCE_GATES"))
        if dataset_node: add_edge(dataset_node, node, "assured_by")
        for run_node in run_nodes.values(): add_edge(run_node, node, "assurance_input")

    bundles = [item for item in _json_models(root / "evidence" / "verification-bundles", VerificationBundle, exclude=("active-bundle.json",)) if isinstance(item, VerificationBundle)]
    for item in bundles:
        node = add_node(LineageNode(id=_node_id("verification-bundle", item.bundle_id), kind="verification_bundle", label="VerificationBundle", detail=f"{item.entry_count} declarative entries", target="EVIDENCE", object_id=str(item.bundle_id), status="INSPECTION_FIRST"))
        add_edge(_node_id("assurance", item.assurance_id), node, "exported_as")

    return LineageGraph(nodes=list(nodes.values()), edges=list(edges.values()))
