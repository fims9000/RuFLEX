import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi, ProductApiError } = vi.hoisted(() => ({ ProductApiError: class ProductApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}, studioApi: {
  evaluateFinalTest: vi.fn(),
  createAnalysisEvaluation: vi.fn(),
  getLatestAnalysisEvaluationForRun: vi.fn(),
  getLatestAnalysisCalibrationForEvaluation: vi.fn(),
  getLatestAnalysisThresholdForEvaluation: vi.fn(),
  getLatestSelectivePolicyForBinding: vi.fn(),
  fitAnalysisCalibration: vi.fn(),
  selectAnalysisThreshold: vi.fn(),
  createSelectivePolicy: vi.fn(),
  createAnalysisComparison: vi.fn(),
  getLatestAnalysisComparison: vi.fn(),
  createSelectedAnalysisComparison: vi.fn(),
  createSliceAnalysis: vi.fn(),
} }));

vi.mock("../../api", () => ({ studioApi, ProductApiError }));
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
  model_spec: { node_count: 2 },
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
  project?: unknown;
  dataset?: unknown;
  datasetHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  datasetHydrationError?: string | null;
  onRetryDatasetHydration?: () => void;
  finalTestEvaluation?: unknown;
  run?: unknown;
  fis?: unknown;
  modelContextStatus?: "idle" | "loading" | "loaded" | "error";
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
  onCalibration?: (calibration: unknown) => void;
  onThreshold?: (threshold: unknown) => void;
  onSelectivePolicy?: (policy: unknown) => void;
} = {}) {
  return render(workspaceElement(readOnly, overrides));
}

function workspaceElement(readOnly = false, overrides: Parameters<typeof renderWorkspace>[1] = {}) {
  return <EvaluationWorkspace
    project={(overrides.project ?? { ...project, read_only: readOnly }) as never} dataset={(overrides.dataset === undefined ? dataset : overrides.dataset) as never} datasetHydrationStatus={overrides.datasetHydrationStatus ?? "available"} datasetHydrationError={overrides.datasetHydrationError ?? null} onRetryDatasetHydration={overrides.onRetryDatasetHydration ?? vi.fn()} fis={(overrides.fis ?? null) as never} modelContextStatus={overrides.modelContextStatus ?? "loaded"} run={(overrides.run === undefined ? run : overrides.run) as never} runs={(overrides.runs ?? [run]) as never} runListStatus={overrides.runListStatus ?? "loaded"} runListError={overrides.runListError ?? null} onRetryRunList={overrides.onRetryRunList ?? vi.fn()} study={null}
    evaluation={(overrides.evaluationStatus === "error" ? null : evaluation) as never} evaluationStatus={overrides.evaluationStatus ?? "available"} evaluationError={overrides.evaluationError ?? null} onRetryEvaluation={overrides.onRetryEvaluation ?? vi.fn()} validationPolicyEvidenceStatus={overrides.validationPolicyEvidenceStatus ?? "available"} validationPolicyEvidenceError={overrides.validationPolicyEvidenceError ?? null} onRetryValidationPolicyEvidence={overrides.onRetryValidationPolicyEvidence ?? vi.fn()} calibrationTransform={null} decisionThreshold={(overrides.decisionThreshold === undefined ? threshold : overrides.decisionThreshold) as never} finalTestEvaluation={(overrides.finalTestEvaluation ?? null) as never}
    finalTestEvidenceStatus={overrides.finalTestEvidenceStatus ?? "none"} finalTestEvidenceError={overrides.finalTestEvidenceError ?? null} onRetryFinalTestEvidence={overrides.onRetryFinalTestEvidence ?? vi.fn()}
    comparison={null} sliceAnalysis={null} selectivePolicy={(overrides.selectivePolicy ?? null) as never} stabilityGatePolicy={(overrides.stabilityGatePolicy ?? null) as never} theme={"light" as never}
    onEvaluation={overrides.onEvaluation ?? vi.fn()} onCalibration={overrides.onCalibration ?? vi.fn()} onThreshold={overrides.onThreshold ?? vi.fn()} onFinalTest={vi.fn()} onComparison={vi.fn()} onSliceAnalysis={vi.fn()} onSelectivePolicy={overrides.onSelectivePolicy ?? vi.fn()}
  />;
}

describe("EvaluationWorkspace final-test boundary", () => {
  it("drops an old project's comparison draft when the project session changes", async () => {
    const fis = { fis_id: "fis-1", semantic_hash: "saved-semantic-hash", system_type: "mamdani", rules: [] };
    const view = renderWorkspace(false, { fis });
    fireEvent.click(screen.getByText(/Manual mamdani FIS/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByText(/logistic_regression · seed/).closest("label")!.querySelector("input")!);
    expect(screen.getByRole("button", { name: "Compare 2 selected models" })).toBeEnabled();
    const newRun = { ...run, run_id: "new-run-123456789" };
    view.rerender(workspaceElement(false, { project: { ...project, session_id: "another-session" }, fis, run: newRun, runs: [newRun] }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Compare 0 selected models" })).toBeDisabled());
    expect(screen.getByText(/Manual mamdani FIS/).closest("label")!.querySelector("input")).not.toBeChecked();
    expect(screen.getByText(/logistic_regression · seed/).closest("label")!.querySelector("input")).not.toBeChecked();
  });

  it("does not offer an old project's uncertain comparison retry in another session", async () => {
    studioApi.createAnalysisComparison.mockReset().mockRejectedValueOnce(new Error("comparison response lost"));
    const fis = { fis_id: "fis-1", semantic_hash: "saved-semantic-hash", system_type: "mamdani", rules: [] };
    const view = renderWorkspace(false, { fis });
    fireEvent.click(screen.getByText(/Manual mamdani FIS/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByText(/logistic_regression · seed/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByRole("button", { name: "Compare 2 selected models" }));
    expect(await screen.findByTestId("comparison-recovery")).toHaveTextContent("comparison response lost");
    const newRun = { ...run, run_id: "new-run-123456789" };
    view.rerender(workspaceElement(false, { project: { ...project, session_id: "another-session" }, fis, run: newRun, runs: [newRun] }));
    await waitFor(() => expect(screen.queryByTestId("comparison-recovery")).not.toBeInTheDocument());
    expect(studioApi.createAnalysisComparison).toHaveBeenCalledTimes(1);
  });

  it("ignores a late comparison failure from the previous project session", async () => {
    let rejectRequest: (error: Error) => void = () => undefined;
    studioApi.createAnalysisComparison.mockReset().mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    const fis = { fis_id: "fis-1", semantic_hash: "saved-semantic-hash", system_type: "mamdani", rules: [] };
    const view = renderWorkspace(false, { fis });
    fireEvent.click(screen.getByText(/Manual mamdani FIS/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByText(/logistic_regression · seed/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByRole("button", { name: "Compare 2 selected models" }));
    const newRun = { ...run, run_id: "new-run-123456789" };
    view.rerender(workspaceElement(false, { project: { ...project, session_id: "another-session" }, fis, run: newRun, runs: [newRun] }));
    await act(async () => { rejectRequest(new Error("old project response lost")); });
    expect(screen.getByRole("button", { name: "Compare 0 selected models" })).toBeDisabled();
    expect(screen.queryByTestId("comparison-recovery")).not.toBeInTheDocument();
    expect(screen.queryByText("old project response lost")).not.toBeInTheDocument();
  });

  it("drops a previous project's slice draft and ignores its late save failure", async () => {
    let rejectRequest: (error: Error) => void = () => undefined;
    studioApi.createSliceAnalysis.mockReset().mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    const view = renderWorkspace();
    fireEvent.change(screen.getByLabelText("Slice name"), { target: { value: "Old project subgroup" } });
    fireEvent.click(screen.getByRole("button", { name: "Run and persist slice" }));
    await waitFor(() => expect(studioApi.createSliceAnalysis).toHaveBeenCalledTimes(1));
    const newRun = { ...run, run_id: "new-run-123456789" };
    view.rerender(workspaceElement(false, { project: { ...project, session_id: "another-session" }, run: newRun, runs: [newRun] }));
    await act(async () => { rejectRequest(new Error("old slice response lost")); });
    expect(screen.getByLabelText("Slice name")).toHaveValue("Validation slice");
    expect(screen.queryByTestId("slice-analysis-recovery")).not.toBeInTheDocument();
    expect(screen.queryByText("old slice response lost")).not.toBeInTheDocument();
  });

  it("never carries final-test confirmation or a late opening error into another project", async () => {
    let rejectRequest: (error: Error) => void = () => undefined;
    studioApi.evaluateFinalTest.mockReset().mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    const view = renderWorkspace();
    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    fireEvent.click(screen.getByRole("button", { name: "Evaluate frozen final test" }));
    await waitFor(() => expect(studioApi.evaluateFinalTest).toHaveBeenCalledTimes(1));
    const newRun = { ...run, run_id: "new-run-123456789" };
    view.rerender(workspaceElement(false, { project: { ...project, session_id: "another-session" }, run: newRun, runs: [newRun] }));
    await act(async () => { rejectRequest(new Error("old final-test response lost")); });
    expect(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ })).not.toBeChecked();
    expect(screen.queryByTestId("final-test-recovery")).not.toBeInTheDocument();
    expect(screen.queryByText("old final-test response lost")).not.toBeInTheDocument();
  });

  it("compares one selected run with one saved manual FIS on validation", async () => {
    studioApi.createAnalysisComparison.mockClear().mockResolvedValueOnce({ comparison_id: "comparison-1", fis_id: "fis-1", fis_semantic_hash: "saved-semantic-hash" } as never);
    renderWorkspace(false, { fis: { fis_id: "fis-1", semantic_hash: "saved-semantic-hash", system_type: "mamdani", rules: [] } });
    const manual = screen.getByText(/Manual mamdani FIS/).closest("label")?.querySelector("input");
    const training = screen.getByText(/logistic_regression · seed/).closest("label")?.querySelector("input");
    expect(manual).not.toBeNull();
    expect(training).not.toBeNull();
    fireEvent.click(manual!);
    fireEvent.click(training!);
    const compare = screen.getByRole("button", { name: "Compare 2 selected models" });
    expect(compare).toBeEnabled();
    fireEvent.click(compare);
    await waitFor(() => expect(studioApi.createAnalysisComparison).toHaveBeenCalledWith("session", [run.run_id], true, "fis-1", "saved-semantic-hash"));
  });

  it("does not recover a comparison from a different FIS semantic revision", async () => {
    studioApi.createAnalysisComparison.mockReset().mockRejectedValueOnce(new Error("comparison response lost"));
    studioApi.getLatestAnalysisComparison.mockReset().mockResolvedValueOnce({ run_ids: [run.run_id], fis_id: "fis-1", fis_semantic_hash: "newer-semantic-hash" } as never);
    renderWorkspace(false, { fis: { fis_id: "fis-1", semantic_hash: "saved-semantic-hash", system_type: "mamdani", rules: [] } });
    fireEvent.click(screen.getByText(/Manual mamdani FIS/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByText(/logistic_regression · seed/).closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByRole("button", { name: "Compare 2 selected models" }));
    expect(await screen.findByTestId("comparison-recovery")).toHaveTextContent("comparison response lost");
    fireEvent.click(screen.getByRole("button", { name: "Retry exact comparison lookup" }));
    await waitFor(() => expect(screen.getByTestId("comparison-recovery")).toHaveTextContent("different run/FIS identities"));
    expect(studioApi.createAnalysisComparison).toHaveBeenCalledTimes(1);
  });

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

  it("recovers a persisted threshold by exact Evaluation and calibration after pointer failure", async () => {
    const onThreshold = vi.fn();
    studioApi.selectAnalysisThreshold.mockRejectedValueOnce(new Error("active threshold pointer write failed"));
    studioApi.getLatestAnalysisThresholdForEvaluation.mockResolvedValueOnce(threshold);
    renderWorkspace(false, { onThreshold });

    fireEvent.click(screen.getByRole("button", { name: "Reselect threshold" }));
    expect(await screen.findByTestId("validation-policy-recovery")).toHaveTextContent("active threshold pointer write failed");
    fireEvent.click(screen.getByRole("button", { name: "Retry exact saved policy lookup" }));

    await waitFor(() => expect(onThreshold).toHaveBeenCalledWith(threshold));
    expect(studioApi.getLatestAnalysisThresholdForEvaluation).toHaveBeenCalledWith("session", evaluation.evaluation_id, null);
    expect(screen.queryByTestId("validation-policy-recovery")).not.toBeInTheDocument();
  });

  it("recovers calibration only through the exact Evaluation lookup", async () => {
    const calibration = { calibration_id: "calibration-1", evaluation_id: evaluation.evaluation_id, run_id: evaluation.run_id };
    const onCalibration = vi.fn();
    studioApi.fitAnalysisCalibration.mockRejectedValueOnce(new Error("calibration pointer write failed"));
    studioApi.getLatestAnalysisCalibrationForEvaluation.mockResolvedValueOnce(calibration);
    renderWorkspace(false, { onCalibration });

    fireEvent.click(screen.getByRole("button", { name: "Fit validation calibration" }));
    expect(await screen.findByTestId("validation-policy-recovery")).toHaveTextContent("calibration pointer write failed");
    fireEvent.click(screen.getByRole("button", { name: "Retry exact saved policy lookup" }));

    await waitFor(() => expect(onCalibration).toHaveBeenCalledWith(calibration));
    expect(studioApi.getLatestAnalysisCalibrationForEvaluation).toHaveBeenCalledWith("session", evaluation.evaluation_id);
  });

  it("recovers selective policy using the exact Evaluation, cutoff, calibration and threshold", async () => {
    const policy = { policy_id: "policy-1", evaluation_id: evaluation.evaluation_id, confidence_cutoff: .8, calibration_id: null, class_threshold_id: threshold.threshold_id };
    const onSelectivePolicy = vi.fn();
    studioApi.createSelectivePolicy.mockRejectedValueOnce(new Error("selective pointer write failed"));
    studioApi.getLatestSelectivePolicyForBinding.mockResolvedValueOnce(policy);
    renderWorkspace(false, { onSelectivePolicy });

    fireEvent.click(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" }));
    expect(await screen.findByTestId("validation-policy-recovery")).toHaveTextContent("selective pointer write failed");
    fireEvent.click(screen.getByRole("button", { name: "Retry exact saved policy lookup" }));

    await waitFor(() => expect(onSelectivePolicy).toHaveBeenCalledWith(policy));
    expect(studioApi.getLatestSelectivePolicyForBinding).toHaveBeenCalledWith("session", evaluation.evaluation_id, .8, null, threshold.threshold_id);
  });

  it("rejects an empty or out-of-range selective cutoff without any policy write", () => {
    studioApi.createSelectivePolicy.mockClear();
    const view = renderWorkspace();
    const cutoff = screen.getByLabelText("Selective confidence cutoff");
    fireEvent.change(cutoff, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" }));
    expect(screen.getByText(/confidence cutoff must be a finite number between 0.5 and 1.0/)).toBeVisible();
    expect(studioApi.createSelectivePolicy).not.toHaveBeenCalled();
    expect(screen.queryByTestId("validation-policy-recovery")).not.toBeInTheDocument();
    fireEvent.change(cutoff, { target: { value: "0.4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" }));
    expect(studioApi.createSelectivePolicy).not.toHaveBeenCalled();
    view.unmount();
  });

  it("treats a definite selective-policy validation rejection as correctable, not an uncertain save", async () => {
    studioApi.createSelectivePolicy.mockReset().mockRejectedValueOnce(new ProductApiError(422, "DecisionThreshold does not belong to this Evaluation."));
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" }));
    expect(await screen.findByText("DecisionThreshold does not belong to this Evaluation.")).toBeVisible();
    expect(screen.queryByTestId("validation-policy-recovery")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save ACCEPT / REVIEW policy" })).toBeEnabled();
  });

  it("does not invent uncertain calibration or threshold saves after definite API rejections", async () => {
    studioApi.fitAnalysisCalibration.mockReset().mockRejectedValueOnce(new ProductApiError(422, "Validation calibration requires both target classes."));
    studioApi.selectAnalysisThreshold.mockReset().mockRejectedValueOnce(new ProductApiError(404, "The selected calibration object does not exist."));
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "Fit validation calibration" }));
    expect(await screen.findByText("Validation calibration requires both target classes.")).toBeVisible();
    expect(screen.queryByTestId("validation-policy-recovery")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reselect threshold" }));
    expect(await screen.findByText("The selected calibration object does not exist.")).toBeVisible();
    expect(screen.queryByTestId("validation-policy-recovery")).not.toBeInTheDocument();
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
