import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  evaluateFinalTest: vi.fn(),
  createAnalysisEvaluation: vi.fn(),
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
  probability_source: "raw", source_split: "validation", objective: "f1", decisions: [], confusion_matrix: run.confusion_matrix,
};

function renderWorkspace(readOnly = false, overrides: { dataset?: unknown; finalTestEvaluation?: unknown } = {}) {
  return render(<EvaluationWorkspace
    project={{ ...project, read_only: readOnly } as never} dataset={(overrides.dataset ?? null) as never} fis={null} run={run as never} runs={[run] as never} study={null}
    evaluation={evaluation as never} calibrationTransform={null} decisionThreshold={threshold as never} finalTestEvaluation={(overrides.finalTestEvaluation ?? null) as never}
    comparison={null} sliceAnalysis={null} selectivePolicy={null} stabilityGatePolicy={null} theme={"light" as never}
    onEvaluation={vi.fn()} onCalibration={vi.fn()} onThreshold={vi.fn()} onFinalTest={vi.fn()} onComparison={vi.fn()} onSliceAnalysis={vi.fn()} onSelectivePolicy={vi.fn()}
  />);
}

describe("EvaluationWorkspace final-test boundary", () => {
  it("requires explicit confirmation before the frozen final-test operation is callable", async () => {
    studioApi.evaluateFinalTest.mockResolvedValue({ final_test_id: "final", run_id: run.run_id, metrics: {}, test_row_count: 2, policy_identity: "policy", test_case_identity: "case" });
    renderWorkspace();
    const execute = screen.getByRole("button", { name: "Evaluate frozen final test" });
    expect(execute).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I confirm this policy was frozen/ }));
    expect(execute).toBeEnabled();
    fireEvent.click(execute);
    await waitFor(() => expect(studioApi.evaluateFinalTest).toHaveBeenCalledWith("session", evaluation.evaluation_id, null, threshold.threshold_id, null, null));
  });

  it("keeps final-test and validation-mutating controls disabled in a read-only project", () => {
    renderWorkspace(true);
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
