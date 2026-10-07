import type { StabilityGatePolicy, StudyStabilityAnalysis, TrainingStudy } from "../../api";

export function isActiveStudyStabilityAnalysis(
  analysis: StudyStabilityAnalysis | null,
  study: TrainingStudy | null,
): analysis is StudyStabilityAnalysis {
  return Boolean(analysis && study
    && analysis.study_id === study.study_id
    && analysis.selected_run_id === study.selected_run_id);
}

export function isActiveStudyStabilityGate(
  policy: StabilityGatePolicy | null,
  analysis: StudyStabilityAnalysis | null,
  study: TrainingStudy | null,
): policy is StabilityGatePolicy {
  return Boolean(policy && analysis && study
    && policy.study_id === study.study_id
    && policy.stability_analysis_id === analysis.analysis_id
    && policy.selected_run_id === analysis.selected_run_id
    && policy.evaluation_id === analysis.evaluation_id
    && policy.class_threshold_id === analysis.class_threshold_id
    && policy.decision_threshold === analysis.decision_threshold
    && policy.dataset_fingerprint === analysis.dataset_fingerprint
    && policy.dataset_artifact_sha256 === analysis.dataset_artifact_sha256
    && policy.model_kind === analysis.model_kind
    && policy.fit_sample_identity === analysis.evaluation_case_identity
    && policy.run_ids.length === analysis.run_ids.length
    && policy.run_ids.every((runId, index) => runId === analysis.run_ids[index])
    && policy.required_run_support === analysis.case_support_requirement
    && policy.analysis_schema_version === analysis.schema_version
    && policy.calibration_id === null
    && policy.probability_source === "raw"
    && policy.source_split === "validation"
    && policy.min_confidence === 0.9
    && policy.min_class_agreement === 0.8
    && policy.max_probability_std === 0.15
    && policy.test_status === "LOCKED_NOT_EVALUATED");
}
