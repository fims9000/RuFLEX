import { describe, expect, it } from "vitest";
import type { StabilityGatePolicy, StudyStabilityAnalysis, TrainingStudy } from "../../api";
import { isActiveStudyStabilityAnalysis, isActiveStudyStabilityGate } from "./stabilityBinding";

const study = { study_id: "study-1", selected_run_id: "run-1" } as TrainingStudy;
const analysis = {
  analysis_id: "analysis-1", study_id: "study-1", selected_run_id: "run-1", evaluation_id: "evaluation-1",
  class_threshold_id: "threshold-1", decision_threshold: .63, dataset_fingerprint: "dataset-fingerprint",
  dataset_artifact_sha256: "dataset-sha", model_kind: "random_forest", evaluation_case_identity: "validation-cases",
  run_ids: ["run-1", "run-2", "run-3"], case_support_requirement: 3, schema_version: 3,
} as StudyStabilityAnalysis;
const policy = {
  study_id: "study-1", stability_analysis_id: "analysis-1", selected_run_id: "run-1", evaluation_id: "evaluation-1",
  class_threshold_id: "threshold-1", decision_threshold: .63, dataset_fingerprint: "dataset-fingerprint",
  dataset_artifact_sha256: "dataset-sha", model_kind: "random_forest", fit_sample_identity: "validation-cases",
  run_ids: ["run-1", "run-2", "run-3"], required_run_support: 3, analysis_schema_version: 3,
  calibration_id: null, probability_source: "raw", source_split: "validation", min_confidence: .9,
  min_class_agreement: .8, max_probability_std: .15, test_status: "LOCKED_NOT_EVALUATED",
} as StabilityGatePolicy;

describe("Stability Lab evidence binding", () => {
  it("accepts only the selected study's analysis and an exact frozen policy chain", () => {
    expect(isActiveStudyStabilityAnalysis(analysis, study)).toBe(true);
    expect(isActiveStudyStabilityGate(policy, analysis, study)).toBe(true);
  });

  it("rejects analysis from another study or selected run", () => {
    expect(isActiveStudyStabilityAnalysis({ ...analysis, study_id: "other-study" }, study)).toBe(false);
    expect(isActiveStudyStabilityAnalysis({ ...analysis, selected_run_id: "other-run" }, study)).toBe(false);
  });

  it("rejects a gate with altered threshold, run order, or gate criteria", () => {
    expect(isActiveStudyStabilityGate({ ...policy, decision_threshold: .5 }, analysis, study)).toBe(false);
    expect(isActiveStudyStabilityGate({ ...policy, run_ids: ["run-2", "run-1", "run-3"] }, analysis, study)).toBe(false);
    expect(isActiveStudyStabilityGate({ ...policy, max_probability_std: .2 }, analysis, study)).toBe(false);
  });
});
