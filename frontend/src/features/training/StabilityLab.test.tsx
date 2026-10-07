import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  listStudyStabilityAnalyses: vi.fn().mockResolvedValue([]),
  listStabilityGatePolicies: vi.fn().mockResolvedValue([]),
  createAnalysisEvaluation: vi.fn(),
  selectAnalysisThreshold: vi.fn(),
  createStudyStabilityAnalysis: vi.fn(),
  createStabilityGatePolicy: vi.fn(),
} }));

vi.mock("../../api", async (importOriginal) => ({ ...await importOriginal<typeof import("../../api")>(), studioApi }));
vi.mock("../../charts/ChartSurface", () => ({ ChartSurface: () => <div /> }));
vi.mock("../../components/StudioPrimitives", () => ({
  Button: ({ children, view: _view, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { view?: string }) => <button {...props}>{children}</button>,
  EmptyState: ({ title, children }: { title: string; children: React.ReactNode }) => <div><strong>{title}</strong>{children}</div>,
  StatusBadge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

import { StabilityLab } from "./StabilityLab";

const project = { session_id: "session", project_id: "project", name: "Test", description: null, root: "/tmp/test", schema_version: 1, read_only: false, modified_at: "2026-01-01T00:00:00Z" };
const study = { study_id: "study-1", name: "Study", model_kind: "flat_neuro_fuzzy", task: "binary_classification", selection_metric: "f1", selection_split: "validation", selection_rule: "max", seed_runs: [{ run_id: "run-1", split_seed: 42 }], selected_run_id: "run-1", selection_reason: "Highest validation F1", randomness_protocol: "TRAINING_VARIABILITY", split_seed: 42, training_seeds: [1, 2, 3] };
const analysis = {
  schema_version: 2, analysis_id: "analysis-1", study_id: "study-1", dataset_fingerprint: "dataset-fingerprint", dataset_artifact_sha256: "a".repeat(64),
  mode: "TRAINING_VARIABILITY", split_identity: "split-identity", split_seeds: [42], model_kind: "flat_neuro_fuzzy", task: "binary_classification",
  run_ids: ["run-1", "run-2", "run-3"], training_seeds: [1, 2, 3], split_seed: 42, evaluation_case_identity: "validation-cases", evaluation_id: "evaluation-1",
  class_threshold_id: "threshold-1", decision_threshold: 0.37, validation_alignment_status: "EXACT_MATCH", applicability: "APPLICABLE", applicability_reason: null,
  selected_run_id: "run-1", case_count: 0, case_support_requirement: 3, probability_source: "raw", metric_distributions: {}, cases: [], high_confidence_threshold: 0.9,
  unstable_agreement_threshold: 0.8, high_confidence_instability_rate: null, high_confidence_case_count: 0, high_confidence_unstable_case_count: 0, warnings: [], scientific_note: "Validation-only evidence.",
};

function renderStability(loadedAnalysis: typeof analysis | null = null) {
  studioApi.listStudyStabilityAnalyses.mockResolvedValueOnce(loadedAnalysis ? [loadedAnalysis] : []);
  return render(<StabilityLab project={project as never} study={study as never} theme={"light" as never} />);
}

beforeEach(() => {
  studioApi.listStudyStabilityAnalyses.mockReset().mockResolvedValue([]);
  studioApi.listStabilityGatePolicies.mockReset().mockResolvedValue([]);
  studioApi.createAnalysisEvaluation.mockReset();
  studioApi.selectAnalysisThreshold.mockReset();
  studioApi.createStudyStabilityAnalysis.mockReset();
  studioApi.createStabilityGatePolicy.mockReset();
});

describe("StabilityLab persisted evidence writes", () => {
  it("synchronously serializes the multi-step analysis chain and marks the saved analysis", async () => {
    let finishEvaluation!: (value: never) => void;
    studioApi.createAnalysisEvaluation.mockImplementationOnce(() => new Promise((resolve) => { finishEvaluation = resolve as (value: never) => void; }));
    studioApi.selectAnalysisThreshold.mockResolvedValueOnce({ threshold_id: "threshold-1", evaluation_id: "evaluation-1", calibration_id: null, probability_source: "raw" } as never);
    studioApi.createStudyStabilityAnalysis.mockResolvedValueOnce(analysis as never);
    renderStability();

    const create = await screen.findByRole("button", { name: "Create Study Stability Analysis" });
    act(() => {
      create.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      create.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.createAnalysisEvaluation).toHaveBeenCalledTimes(1);
    expect(create).toBeDisabled();
    await act(async () => { finishEvaluation({ evaluation_id: "evaluation-1", run_id: "run-1" } as never); });
    expect(await screen.findByRole("button", { name: "Stability Analysis saved" })).toBeDisabled();
    expect(studioApi.createAnalysisEvaluation).toHaveBeenCalledTimes(1);
    expect(studioApi.selectAnalysisThreshold).toHaveBeenCalledTimes(1);
    expect(studioApi.createStudyStabilityAnalysis).toHaveBeenCalledTimes(1);
  });

  it("synchronously serializes gate freezes and disables an already active exact gate", async () => {
    let finishGate!: (value: never) => void;
    studioApi.createStabilityGatePolicy.mockImplementationOnce(() => new Promise((resolve) => { finishGate = resolve as (value: never) => void; }));
    renderStability(analysis);

    const freeze = await screen.findByRole("button", { name: "Freeze Stability Gate" });
    act(() => {
      freeze.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      freeze.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.createStabilityGatePolicy).toHaveBeenCalledTimes(1);
    expect(freeze).toBeDisabled();
    const savedGate = {
      policy_id: "gate-1", study_id: analysis.study_id, stability_analysis_id: analysis.analysis_id, selected_run_id: analysis.selected_run_id,
      evaluation_id: analysis.evaluation_id, class_threshold_id: analysis.class_threshold_id, decision_threshold: analysis.decision_threshold, calibration_id: null,
      dataset_fingerprint: analysis.dataset_fingerprint, dataset_artifact_sha256: analysis.dataset_artifact_sha256, model_kind: analysis.model_kind,
      source_split: "validation", fit_sample_identity: analysis.evaluation_case_identity, run_ids: analysis.run_ids, required_run_support: analysis.case_support_requirement,
      probability_source: "raw", analysis_schema_version: analysis.schema_version, min_confidence: 0.9, min_class_agreement: 0.8, max_probability_std: 0.15,
      test_status: "LOCKED_NOT_EVALUATED", decisions: [], risk_coverage: [], scientific_note: "Frozen validation gate.",
    };
    await act(async () => { finishGate(savedGate as never); });
    expect(await screen.findByRole("button", { name: "Stability Gate frozen" })).toBeDisabled();
    expect(studioApi.createStabilityGatePolicy).toHaveBeenCalledTimes(1);
  });
});
