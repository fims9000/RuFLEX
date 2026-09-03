from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ruflex.application.datasets import load_dataset_contract, load_dataset_profile
from ruflex.application.evidence import load_explanation, load_explanation_check
from ruflex.application.reproducibility import load_latest_explanation_reproducibility
from ruflex.application.exhaustive import load_latest_exhaustive
from ruflex.application.assurance import load_latest_assurance_case
from ruflex.application.behavior import list_behavior_results, list_behavior_specs, load_latest_behavior_result
from ruflex.application.selective import load_latest_selective_policy
from ruflex.application.stability import list_stability_gate_policies, list_study_stability_analyses, load_stability_gate_policy, load_study_stability_analysis
from ruflex.domain.behavior import BehaviorSpec, BehaviorSpecResult
from ruflex.application.expert_correction import load_expert_correction
from ruflex.application.fis import load_fis, list_fis_revisions
from ruflex.application.generalization import (
    GeneralizationContract,
    SliceAnalysis,
    load_generalization_contract,
    load_slice_analysis,
)
from ruflex.application.lineage import build_project_lineage
from ruflex.application.project_integrity import inspect_project_integrity
from ruflex.application.verification_bundle import validate_verification_bundle
from ruflex.application.projects import ProjectService
from ruflex.application.training import (
    list_training_runs,
    load_decision_threshold,
    load_final_test_evaluation,
    load_validation_calibration,
    load_validation_comparison,
    load_validation_evaluation,
)
from ruflex.domain.evidence import ExplanationCheck, ExplanationContract, ExplanationReproducibilityAnalysis
from ruflex.domain.exhaustive import ExhaustiveLabResult
from ruflex.domain.assurance import AssuranceCase
from ruflex.domain.selective import SelectivePredictionPolicy
from ruflex.domain.stability import StabilityGatePolicy, StudyStabilityAnalysis
from ruflex.domain.expert_correction import ExpertCorrectionRevision
from ruflex.domain.lineage import LineageGraph
from ruflex.domain.project import ProjectIntegrityReport
from ruflex.domain.verification import VerificationBundleValidation
from ruflex.domain.training import (
    AnalysisComparison,
    AnalysisEvaluation,
    CalibrationTransform,
    DecisionThresholdPolicy,
    FinalTestEvaluation,
    TrainingRun,
)


class StudioProjectView:
    """Read-only Python view over the same canonical project objects used by Studio."""

    def __init__(self, path: str | Path) -> None:
        self._project = ProjectService().open(Path(path), read_only=True)

    @property
    def root(self) -> Path:
        return self._project.root

    @property
    def manifest(self):
        return self._project.manifest

    def dataset_contract(self):
        return load_dataset_contract(self.root)

    def dataset_profile(self):
        return load_dataset_profile(self.root)

    def active_fis(self):
        return load_fis(self.root)

    def fis_revisions(self):
        return list_fis_revisions(self.root)

    def training_runs(self) -> list[TrainingRun]:
        return list_training_runs(self.root)

    def evaluation(self, evaluation_id: UUID | str) -> AnalysisEvaluation:
        return load_validation_evaluation(self.root, UUID(str(evaluation_id)))

    def calibration(self, calibration_id: UUID | str) -> CalibrationTransform:
        return load_validation_calibration(self.root, UUID(str(calibration_id)))

    def threshold(self, threshold_id: UUID | str) -> DecisionThresholdPolicy:
        return load_decision_threshold(self.root, UUID(str(threshold_id)))

    def final_test(self, final_test_id: UUID | str) -> FinalTestEvaluation:
        return load_final_test_evaluation(self.root, UUID(str(final_test_id)))

    def comparison(self, comparison_id: UUID | str) -> AnalysisComparison:
        return load_validation_comparison(self.root, UUID(str(comparison_id)))

    def slice_analysis(self, analysis_id: UUID | str) -> SliceAnalysis:
        return load_slice_analysis(self.root, UUID(str(analysis_id)))

    def explanation(self, explanation_id: UUID | str) -> ExplanationContract:
        return load_explanation(self.root, UUID(str(explanation_id)))

    def explanation_check(self, check_id: UUID | str) -> ExplanationCheck:
        return load_explanation_check(self.root, UUID(str(check_id)))

    def latest_explanation_reproducibility(self) -> ExplanationReproducibilityAnalysis:
        return load_latest_explanation_reproducibility(self.root)

    def latest_exhaustive_lab(self) -> ExhaustiveLabResult:
        return load_latest_exhaustive(self.root)

    def latest_assurance_case(self) -> AssuranceCase:
        return load_latest_assurance_case(self.root)

    def latest_behavior_result(self) -> BehaviorSpecResult:
        return load_latest_behavior_result(self.root)

    def latest_selective_policy(self) -> SelectivePredictionPolicy:
        return load_latest_selective_policy(self.root)

    def stability_analysis(self, analysis_id: UUID | str) -> StudyStabilityAnalysis:
        return load_study_stability_analysis(self.root, UUID(str(analysis_id)))

    def stability_analyses(self) -> list[StudyStabilityAnalysis]:
        return list_study_stability_analyses(self.root)

    def stability_gate_policy(self, policy_id: UUID | str) -> StabilityGatePolicy:
        return load_stability_gate_policy(self.root, UUID(str(policy_id)))

    def stability_gate_policies(self) -> list[StabilityGatePolicy]:
        return list_stability_gate_policies(self.root)

    def behavior_specs(self) -> list[BehaviorSpec]:
        return list_behavior_specs(self.root)

    def behavior_results(self) -> list[BehaviorSpecResult]:
        return list_behavior_results(self.root)

    def expert_correction(self, correction_id: UUID | str) -> ExpertCorrectionRevision:
        return load_expert_correction(self.root, UUID(str(correction_id)))

    def generalization_contract(self, contract_id: UUID | str | None = None) -> GeneralizationContract:
        """Load a persisted generalization contract from the same Studio project.

        When no id is supplied the active contract recorded in the project
        manifest is used.  The SDK stays read-only and never creates a new
        protocol implicitly.
        """
        resolved = contract_id or self._project.manifest.active_generalization_contract_id
        if resolved is None:
            raise FileNotFoundError("This project has no active generalization contract.")
        return load_generalization_contract(self.root, UUID(str(resolved)))

    def lineage(self) -> LineageGraph:
        return build_project_lineage(self.root)

    def integrity(self) -> ProjectIntegrityReport:
        return inspect_project_integrity(self.root)


def open_studio_project(path: str | Path) -> StudioProjectView:
    """Open a Studio workspace read-only without creating a browser/API session."""
    return StudioProjectView(path)


def validate_bundle(path: str | Path) -> VerificationBundleValidation:
    """Read-only, portable inspection of a VerificationBundle ZIP or directory."""
    return validate_verification_bundle(path)
