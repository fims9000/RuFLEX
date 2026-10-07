import "@testing-library/jest-dom/vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  listBehaviorResults: vi.fn().mockResolvedValue([]),
  listBehaviorRevisionComparisons: vi.fn().mockResolvedValue([]),
  getLatestConditionMonitoringDemo: vi.fn().mockResolvedValue(null),
  listPosthocExplanationJobs: vi.fn().mockResolvedValue([]),
  listExplanations: vi.fn().mockResolvedValue([]),
  getPluginCatalog: vi.fn().mockResolvedValue([]),
  getRuntimeExplainers: vi.fn().mockResolvedValue([]),
  getRuntimeValidators: vi.fn().mockResolvedValue([]),
  getRuntimeBackends: vi.fn().mockResolvedValue([{ identity: { key: "local_executor", provider: "ruflex.builtin" } }]),
  getTrainingRunCapabilities: vi.fn().mockResolvedValue({ decisions: [{ capability: "occlusion", status: "AVAILABLE", detail: "native method" }] }),
  startPosthocExplanationJob: vi.fn(),
  getPosthocExplanationJob: vi.fn(),
} }));

vi.mock("../../api", async (importOriginal) => ({ ...await importOriginal<typeof import("../../api")>(), studioApi }));
vi.mock("../../components/StudioPrimitives", () => ({
  Button: ({ children, view: _view, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { view?: string }) => <button {...props}>{children}</button>,
  EmptyState: ({ title, children }: { title: string; children: React.ReactNode }) => <div><strong>{title}</strong>{children}</div>,
  StatusBadge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  TextInput: ({ value, onUpdate, ...props }: { value: string; onUpdate: (value: string) => void; [key: string]: unknown }) => <input {...props} value={value} onChange={(event) => onUpdate(event.target.value)} />,
}));
vi.mock("../modelbuild/TraceWorkspace", () => ({ TraceWorkspace: () => <div /> }));

import { EvidenceWorkspace } from "./EvidenceWorkspace";

const project = { session_id: "session", project_id: "project", name: "Test", description: null, root: "/tmp/test", schema_version: 1, read_only: false, modified_at: "2026-01-01T00:00:00Z" };
const run = { run_id: "run-1", model_kind: "flat_neuro_fuzzy", task: "binary_classification", feature_columns: ["x"], validation_metrics: {}, prediction_preview: [], seed: 7 };

function renderEvidence() {
  return render(<EvidenceWorkspace
    project={project as never} dataset={null} run={run as never} evaluation={null} previousEvaluation={null} treeEvidence={null}
    explanation={null} explanationCheck={null} behaviorSpec={null} lineageBehaviorComparison={null} behaviorResult={null}
    reproducibility={null} exhaustive={null} assurance={null} verificationBundleRecord={null} selectivePolicy={null} generalization={null}
    theme={"light" as never} onExplanation={vi.fn()} onExplanationCheck={vi.fn()} onBehaviorResult={vi.fn()} onReproducibility={vi.fn()}
    onExhaustive={vi.fn()} onAssurance={vi.fn()}
  />);
}

beforeEach(() => {
  studioApi.listBehaviorResults.mockReset().mockResolvedValue([]);
  studioApi.listBehaviorRevisionComparisons.mockReset().mockResolvedValue([]);
  studioApi.getLatestConditionMonitoringDemo.mockReset().mockResolvedValue(null);
  studioApi.listPosthocExplanationJobs.mockReset().mockResolvedValue([]);
  studioApi.listExplanations.mockReset().mockResolvedValue([]);
  studioApi.getPluginCatalog.mockReset().mockResolvedValue([]);
  studioApi.getRuntimeExplainers.mockReset().mockResolvedValue([]);
  studioApi.getRuntimeValidators.mockReset().mockResolvedValue([]);
  studioApi.getRuntimeBackends.mockReset().mockResolvedValue([{ identity: { key: "local_executor", provider: "ruflex.builtin" } }]);
  studioApi.getTrainingRunCapabilities.mockReset().mockResolvedValue({ decisions: [{ capability: "occlusion", status: "AVAILABLE", detail: "native method" }] });
  studioApi.startPosthocExplanationJob.mockReset();
  studioApi.getPosthocExplanationJob.mockReset();
});

describe("EvidenceWorkspace persisted explanation jobs", () => {
  it("serializes exact saved-job resume before React rerenders", async () => {
    const savedJob = { job_id: "job-saved", kind: "explanation_generation", status: "queued", message: "Queued", error: null, output: {} };
    studioApi.listPosthocExplanationJobs.mockResolvedValueOnce([savedJob] as never);
    studioApi.getPosthocExplanationJob.mockResolvedValueOnce({ ...savedJob, status: "failed", error: "worker stopped" } as never);
    renderEvidence();

    const resume = await screen.findByRole("button", { name: "Resume saved job" });
    act(() => {
      resume.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      resume.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitFor(() => expect(studioApi.getPosthocExplanationJob).toHaveBeenCalledTimes(1));
    expect(studioApi.startPosthocExplanationJob).not.toHaveBeenCalled();
  });

  it("synchronously rejects duplicate explanation generation before React rerenders", async () => {
    const queuedJob = { job_id: "job-1", kind: "explanation_generation", status: "queued", message: "Queued", error: null, output: {} };
    let finishStart!: (value: never) => void;
    studioApi.startPosthocExplanationJob.mockImplementationOnce(() => new Promise((resolve) => { finishStart = resolve as (value: never) => void; }));
    studioApi.getPosthocExplanationJob.mockRejectedValueOnce(new Error("job status temporarily unavailable"));
    renderEvidence();

    const generate = await screen.findByRole("button", { name: "Generate explanation" });
    await waitFor(() => expect(generate).toBeEnabled());
    act(() => {
      generate.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      generate.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.startPosthocExplanationJob).toHaveBeenCalledTimes(1);
    expect(generate).toBeDisabled();
    await act(async () => { finishStart(queuedJob as never); });
    expect(await screen.findByRole("button", { name: "Resume saved job" })).toBeInTheDocument();
    expect(studioApi.startPosthocExplanationJob).toHaveBeenCalledTimes(1);
  });
});
