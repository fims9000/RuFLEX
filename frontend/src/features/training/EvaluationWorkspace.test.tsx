import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  evaluateFinalTest: vi.fn(),
  createAnalysisEvaluation: vi.fn(),
  getLatestAnalysisEvaluationForRun: vi.fn(),
  fitAnalysisCalibration: vi.fn(),
  selectAnalysisThreshold: vi.fn(),
  createSelectivePolicy: vi.fn(),
  createAnalysisComparison: vi.fn(),
  createSelectedAnalysisComparison: vi.fn(),
  createSliceAnalysis: vi.fn(),
} }));

vi.mock("../../api", () => ({ studioApi }));
vi.mock("../../components/StudioPrimitives", () => ({
  Button: ({ children, view: _view, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { view?: string }) => <button {...props}>{children}</button>,
  EmptyState: ({ title, children }: { title: string; children: React.ReactNode }) => <div><strong>{title}</strong>{children}</div>,
  StatusBadge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("../../charts/ChartSurface", () => ({ ChartSurface: () => <div data-testid="chart" /> }));

import { EvaluationWorkspace } from "./EvaluationWorkspace";

const project = { session_id: "session", project_id: "project", name: "Test", description: null, root: "/tmp/test", schema_version: 1, read_only: false, modified_at: "2026-01-01T00:00:00Z" };
const run = {
  run_id: "run-123456789012", model_kind: "logistic_regression", task: "binary_classification", target: "target",
  model_artifact_sha256: "a".repeat(64), scientific_note: "validation only", split: { test_count: 2 },
  validation_metrics: { f1: .8 }, calibration: [], prediction_preview: [], confusion_matrix: { true_negative: 1, false_positive: 0, false_negative: 0, true_positive: 1 },
};
const evaluation = {
  evaluation_id: "evaluation-123456789", run_id: run.run_id, scientific_note: "persisted validation", metrics: { f1: .8 }, calibration_bins: [],
  roc_curve: [], precision_recall_curve: [], prediction_preview: [], validation_row_count: 2, confusion_matrix: run.confusion_matrix,
};
const threshold = {
  threshold_id: "threshold-123456789", evaluation_id: evaluation.evaluation_id, selected_threshold: .6, selection_result: .8,
  probability_source: "raw", calibration_id: null, source_split: "validation", objective: "f1", decisions: [], confusion_matrix: run.confusion_matrix,
};
const dataset = {
  contract: { dataset_fingerprint: "dataset-fingerprint", source_artifact_sha256: "dataset-artifact", feature_columns: ["feature"] },
  profile: { columns: [{ name: "feature" }] },
};

function renderWorkspace(readOnly = false, overrides: {
  dataset?: unknown;
  datasetHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  datasetHydrationError?: string | null;
  onRetryDatasetHydration?: () => void;
  finalTestEvaluation?: unknown;
  run?: unknown;
  runs?: unknown[];
  runListStatus?: "idle" | "loading" | "loaded" | "error";
  runListError?: string | null;
  onRetryRunList?: () => void;
  finalTestEvidenceStatus?: "idle" | "loading" | "none" | "available" | "error";
  finalTestEvidenceError?: string | null;
  onRetryFinalTestEvidence?: () => void;
  evaluationStatus?: "idle" | "loading" | "none" | "available" | "error";
  evaluationError?: string | null;
  decisionThreshold?: unknown;
  selectivePolicy?: unknown;
  stabilityGatePolicy?: unknown;
  onRetryEvaluation?: () => void;
  validationPolicyEvidenceStatus?: "idle" | "loading" | "available" | "error";
  validationPolicyEvidenceError?: string | null;
  onRetryValidationPolicyEvidence?: () => void;
  onEvaluation?: (evaluation: unknown) => void;
} = {}) {
  return render(<EvaluationWorkspace
    project={{ ...project, read_only: readOnly } as never} dataset={(overrides.dataset === undefined ? dataset : overrides.dataset) as never} datasetHydrationStatus={overrides.datasetHydrationStatus ?? "available"} datasetHydrationError={overrides.datasetHydrationError ?? null} onRetryDatasetHydration={overrides.onRetryDatasetHydration ?? vi.fn()} fis={null} run={(overrides.run === undefined ? run : overrides.run) as never} runs={(overrides.runs ?? [run]) as never} runListStatus={overrides.runListStatus ?? "loaded"} runListError={overrides.runListError ?? null} onRetryRunList={overrides.onRetryRunList ?? vi.fn()} study={null}
    evaluation={(overrides.evaluationStatus === "error" ? null : evaluation) as never} evaluationStatus={overrides.evaluationStatus ?? "available"} evaluationError={overrides.evaluationError ?? null} onRetryEvaluation={overrides.onRetryEvaluation ?? vi.fn()} validationPolicyEvidenceStatus={overrides.validationPolicyEvidenceStatus ?? "available"} validationPolicyEvidenceError={overrides.validationPolicyEvidenceError ?? null} onRetryValidationPolicyEvidence={overrides.onRetryValidationPolicyEvidence ?? vi.fn()} calibrationTransform={null} decisionThreshold={(overrides.decisionThreshold === undefined ? threshold : overrides.decisionThreshold) as never} finalTestEvaluation={(overrides.finalTestEvaluation ?? null) as never}
    finalTestEvidenceStatus={overrides.finalTestEvidenceStatus ?? "none"} finalTestEvidenceError={overrides.finalTestEvidenceError ?? null} onRetryFinalTestEvidence={overrides.onRetryFinalTestEvidence ?? vi.fn()}
    comparison={null} sliceAnalysis={null} selectivePolicy={(overrides.selectivePolicy ?? null) as never} stabilityGatePolicy={(overrides.stabilityGatePolicy ?? null) as never} theme={"light" as never}
    onEvaluation={overrides.onEvaluation ?? vi.fn()} onCalibration={vi.fn()} onThreshold={vi.fn()} onFinalTest={vi.fn()} onComparison={vi.fn()} onSliceAnalysis={vi.fn()} onSelectivePolicy={vi.fn()}
  />);
}

describe("EvaluationWorkspace final-test boundary", () => {
  it("recovers a persisted Evaluation by its exact run when the active pointer write failed", async () => {
    const onEvaluation = vi.fn();
    studioApi.createAnalysisEvaluation.mockRejectedValueOnce(new Error("active-evaluation pointer write failed"));
    studioApi.getLatestAnalysisEvaluationForRun.mockResolvedValueOnce(evaluation);
    renderWorkspace(false, { onEvaluation });

    fireEvent.click(screen.getByRole("button", { name: "Save evaluation revision" }));
    const recovery = await screen.findByTestId("evaluation-recovery");
    expect(recovery).toHaveTextContent("active-evaluation pointer write failed");
    fireEvent.click(screen.getByRole("button", { name: "Retry saved Evaluation lookup" }));

    await waitFor(() => expect(onEvaluation).toHaveBeenCalledWith(evaluation));
    expect(studioApi.getLatestAnalysisEvaluationForRun).toHaveBeenCalledWith("session", run.run_id);
    expect(screen.queryByTestId("evaluation-recovery")).not.toBeInTheDocument();
  });

  it("labels the default 0.50 confusion matrix as a preview rather than a frozen threshold policy", () => {
    renderWorkspace(false, { decisionThreshold: null });
    expect(screen.getByRole("heading", { name: "Preview at default cutoff 0.50 · no frozen threshold policy" })).toBeVisible();
    expect(screen.queryByText("Frozen policy threshold 0.60")).not.toBeInTheDocument();
  });

  it("identifies a persisted validation threshold as the frozen policy cutoff", () => {
    renderWorkspace();
    expect(screen.getByRole("heading", { name: "Frozen policy threshold 0.60" })).toBeVisible();
  });

  it("keeps dataset-dependent policy and final-test actions paused until dataset identity is restored", () => {
    const retry = vi.fn();
    renderWorkspace(false, { datasetHydrationStatus: "error", datasetHydrationError: "dataset store unavailable", onRetryDatasetHydration: retry });
    expect(screen.getByRole("alert")).toHaveTextContent("Could not verify the persisted DatasetContract");
    expect(screen.getByRole("alert")).toHaveTextContent("dataset store unavailable");
    expect(screen.getByText("0.8000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reselect threshold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Evaluate frozen final test" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry dataset check" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("does not infer missing frozen policies when policy hydration fails", () => {
    const retry = vi.fn();
    renderWorkspace(false, { validationPolicyEvidenceStatus: "error", validationPolicyEvidenceError: "threshold store unavailable", onRetryValidationPolicyEvidence: retry });
    expect(screen.getByRole("alert")).toHaveTextContent("Could not verify saved validation policies");
    expect(screen.getByRole("alert")).toHaveTextContent("threshold store unavailable");
    expect(screen.getByRole("button", { name: "Save evaluation revision" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reselect threshold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    expect(screen.getByRole("button", { name: "Evaluate frozen final test" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry saved policy check" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("preserves run metrics but pauses new Evaluation and policy writes while saved Evaluation lookup fails", () => {
    const retry = vi.fn();
    renderWorkspace(false, { evaluationStatus: "error", evaluationError: "evaluation store unavailable", onRetryEvaluation: retry });
    expect(screen.getByRole("alert")).toHaveTextContent("Could not verify saved validation Evaluation");
    expect(screen.getByRole("alert")).toHaveTextContent("evaluation store unavailable");
    expect(screen.getByText("0.8000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save validation evidence" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Fit validation calibration" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Select F1 threshold (raw)" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry validation evidence check" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("fails closed when persisted final-test access status cannot be verified", () => {
    const retry = vi.fn();
    renderWorkspace(false, { finalTestEvidenceStatus: "error", finalTestEvidenceError: "API unavailable", onRetryFinalTestEvidence: retry });
    expect(screen.getByRole("heading", { name: "Final-test state unavailable" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not verify whether final-test access already occurred");
    expect(screen.getByRole("button", { name: "Reselect threshold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Fit validation calibration" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    expect(screen.getByRole("button", { name: "Evaluate frozen final test" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry final-test status check" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("does not misreport a run-list request failure as an empty project", () => {
    const retry = vi.fn();
    renderWorkspace(false, { run: null, runs: [], runListStatus: "error", runListError: "API unavailable", onRetryRunList: retry });
    expect(screen.getByRole("alert")).toHaveTextContent("Could not restore saved training runs");
    expect(screen.getByRole("alert")).toHaveTextContent("API unavailable");
    expect(screen.queryByText("No trained run")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading saved runs" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("requires explicit confirmation before the frozen final-test operation is callable", async () => {
    studioApi.evaluateFinalTest.mockResolvedValue({ final_test_id: "final", run_id: run.run_id, metrics: {}, test_row_count: 2, policy_identity: "policy", test_case_identity: "case" });
    renderWorkspace(false, {
      selectivePolicy: { policy_id: "old-selective", evaluation_id: "old-evaluation", run_id: "old-run", calibration_id: null, class_threshold_id: "old-threshold", class_threshold: .6, fit_sample_identity: "old-samples", confidence_cutoff: .8, probability_source: "raw", risk_coverage: [], scientific_note: "old policy" },
      stabilityGatePolicy: { policy_id: "old-stability", evaluation_id: "old-evaluation", selected_run_id: "old-run", class_threshold_id: "old-threshold", calibration_id: null, dataset_fingerprint: "old-dataset", dataset_artifact_sha256: "old-artifact" },
    });
    expect(screen.getByText(/saved selective policy belongs to a different run/)).toHaveAttribute("role", "status");
    expect(screen.getByText(/saved Stability Gate is bound to a different run/)).toHaveAttribute("role", "status");
    const execute = screen.getByRole("button", { name: "Evaluate frozen final test" });
    expect(execute).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    expect(execute).toBeEnabled();
    fireEvent.click(execute);
    await waitFor(() => expect(studioApi.evaluateFinalTest).toHaveBeenCalledWith("session", evaluation.evaluation_id, null, threshold.threshold_id, null, null));
  });

  it("passes only exact Evaluation/run/dataset-bound frozen policies to final-test application", async () => {
    studioApi.evaluateFinalTest.mockResolvedValue({ final_test_id: "final", run_id: run.run_id, metrics: {}, test_row_count: 2, policy_identity: "policy", test_case_identity: "case" });
    renderWorkspace(false, {
      selectivePolicy: { policy_id: "selective-current", evaluation_id: evaluation.evaluation_id, run_id: run.run_id, calibration_id: null, class_threshold_id: threshold.threshold_id, class_threshold: threshold.selected_threshold, fit_sample_identity: "validation-cases", confidence_cutoff: .8, probability_source: "raw", risk_coverage: [], scientific_note: "frozen validation policy" },
      stabilityGatePolicy: { policy_id: "stability-current", evaluation_id: evaluation.evaluation_id, selected_run_id: run.run_id, class_threshold_id: threshold.threshold_id, calibration_id: null, dataset_fingerprint: dataset.contract.dataset_fingerprint, dataset_artifact_sha256: dataset.contract.source_artifact_sha256 },
    });

    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    fireEvent.click(screen.getByRole("button", { name: "Evaluate frozen final test" }));
    await waitFor(() => expect(studioApi.evaluateFinalTest).toHaveBeenCalledWith("session", evaluation.evaluation_id, null, threshold.threshold_id, "selective-current", "stability-current"));
  });

  it("keeps final-test and validation-mutating controls disabled in a read-only project", () => {
    renderWorkspace(true);
    expect(screen.getByRole("status")).toHaveTextContent("saved validation evidence is available to inspect");
    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    expect(screen.getByRole("button", { name: "Evaluate frozen final test" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Save evaluation revision/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Reselect threshold/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" })).toBeDisabled();
  });

  it("shows an already-opened dataset boundary when the current run has no final-test result", () => {
    renderWorkspace(false, {
      dataset: {
        contract: { dataset_fingerprint: "dataset-fingerprint", feature_columns: ["feature"] },
        profile: { columns: [{ name: "feature" }] },
      },
      finalTestEvaluation: {
        run_id: "another-run",
        dataset_fingerprint: "dataset-fingerprint",
        dataset_test_unlock_at: "2026-10-06T10:00:00Z",
      },
    });

    expect(screen.getByRole("heading", { name: "Dataset final-test boundary already opened" })).toBeInTheDocument();
    expect(screen.getByText(/This run has no persisted FinalTestEvaluation/)).toBeInTheDocument();
    expect(screen.getByText(/Dataset test gate opened/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reselect threshold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" })).toBeDisabled();
  });

  it("does not apply an older dataset revision's final-test boundary to the active dataset", () => {
    renderWorkspace(false, {
      dataset: {
        contract: { dataset_fingerprint: "new-dataset-revision", feature_columns: ["feature"] },
        profile: { columns: [{ name: "feature" }] },
      },
      finalTestEvaluation: {
        run_id: "old-run",
        dataset_fingerprint: "old-dataset-revision",
        dataset_test_unlock_at: "2026-10-06T10:00:00Z",
      },
    });

    expect(screen.getByRole("heading", { name: "Final test remains closed" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reselect threshold" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" })).toBeEnabled();
  });
});
