import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  listBehaviorResults: vi.fn().mockResolvedValue([]),
  listBehaviorRevisionComparisons: vi.fn().mockResolvedValue([]),
  createBehaviorSpec: vi.fn(),
  listBehaviorSpecs: vi.fn().mockResolvedValue([]),
  runBehaviorSpec: vi.fn(),
  compareBehaviorResults: vi.fn(),
  createExplanationReproducibility: vi.fn(),
  runExhaustiveLab: vi.fn(),
  getLatestConditionMonitoringDemo: vi.fn().mockResolvedValue(null),
  runConditionMonitoringDemo: vi.fn(),
  listPosthocExplanationJobs: vi.fn().mockResolvedValue([]),
  listExplanations: vi.fn().mockResolvedValue([]),
  getPluginCatalog: vi.fn().mockResolvedValue([]),
  getRuntimeExplainers: vi.fn().mockResolvedValue([]),
  getRuntimeValidators: vi.fn().mockResolvedValue([]),
  getRuntimeBackends: vi.fn().mockResolvedValue([{ identity: { key: "local_executor", provider: "ruflex.builtin" } }]),
  getTrainingRunCapabilities: vi.fn().mockResolvedValue({ decisions: [{ capability: "occlusion", status: "AVAILABLE", detail: "native method" }] }),
  startAssuranceCaseJob: vi.fn(),
  startVerificationBundleJob: vi.fn(),
  cancelEvidenceJob: vi.fn(),
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

function renderEvidence(assurance: unknown = null, selectivePolicy: unknown = null, trainingRun: unknown = run) {
  return render(<EvidenceWorkspace
    project={project as never} dataset={null} fis={null} run={trainingRun as never} evaluation={null} previousEvaluation={null} treeEvidence={null}
    explanation={null} explanationCheck={null} behaviorSpec={null} lineageBehaviorComparison={null} behaviorResult={null}
    reproducibility={null} exhaustive={null} assurance={assurance as never} verificationBundleRecord={null} selectivePolicy={selectivePolicy as never} generalization={null}
    theme={"light" as never} onExplanation={vi.fn()} onExplanationCheck={vi.fn()} onBehaviorResult={vi.fn()} onReproducibility={vi.fn()}
    onExhaustive={vi.fn()} onAssurance={vi.fn()}
  />);
}

beforeEach(() => {
  studioApi.listBehaviorResults.mockReset().mockResolvedValue([]);
  studioApi.listBehaviorRevisionComparisons.mockReset().mockResolvedValue([]);
  studioApi.createBehaviorSpec.mockReset();
  studioApi.listBehaviorSpecs.mockReset().mockResolvedValue([]);
  studioApi.runBehaviorSpec.mockReset();
  studioApi.compareBehaviorResults.mockReset();
  studioApi.runExhaustiveLab.mockReset();
  studioApi.createExplanationReproducibility.mockReset();
  studioApi.getLatestConditionMonitoringDemo.mockReset().mockResolvedValue(null);
  studioApi.runConditionMonitoringDemo.mockReset();
  studioApi.listPosthocExplanationJobs.mockReset().mockResolvedValue([]);
  studioApi.listExplanations.mockReset().mockResolvedValue([]);
  studioApi.getPluginCatalog.mockReset().mockResolvedValue([]);
  studioApi.getRuntimeExplainers.mockReset().mockResolvedValue([]);
  studioApi.getRuntimeValidators.mockReset().mockResolvedValue([]);
  studioApi.getRuntimeBackends.mockReset().mockResolvedValue([{ identity: { key: "local_executor", provider: "ruflex.builtin" } }]);
  studioApi.getTrainingRunCapabilities.mockReset().mockResolvedValue({ decisions: [{ capability: "occlusion", status: "AVAILABLE", detail: "native method" }] });
  studioApi.startAssuranceCaseJob.mockReset();
  studioApi.startVerificationBundleJob.mockReset();
  studioApi.cancelEvidenceJob.mockReset();
  studioApi.getPosthocExplanationJob.mockReset();
  studioApi.startPosthocExplanationJob.mockReset();
});

describe("EvidenceWorkspace persisted explanation jobs", () => {
  it("submits one exhaustive analysis for duplicate synchronous events", async () => {
    let rejectExhaustive!: (error: Error) => void;
    studioApi.runExhaustiveLab.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectExhaustive = reject; }));
    renderEvidence(null, null, { ...run, model_kind: "decision_tree" });

    const enumerate = await screen.findByRole("button", { name: "Enumerate exact Decision Tree paths" });
    act(() => {
      enumerate.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      enumerate.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.runExhaustiveLab).toHaveBeenCalledTimes(1);
    expect(studioApi.runExhaustiveLab).toHaveBeenCalledWith("session", "decision_tree_structure", "run-1", 3, 10000);
    expect(enumerate).toBeDisabled();
    await act(async () => { rejectExhaustive(new Error("result response unavailable")); });
    expect(await screen.findByTestId("exhaustive-recovery")).toHaveTextContent("result response unavailable");
  });

  it("submits one reproducibility analysis for the frozen selected explanation IDs", async () => {
    const explanations = ["exp-a", "exp-b", "exp-c", "exp-d"].map((explanation_id, index) => ({ explanation_id, run_id: `run-${index % 2}`, method: "occlusion", sample_identity: "case-1" }));
    studioApi.listExplanations.mockReset().mockResolvedValue(explanations as never);
    let rejectAnalysis!: (error: Error) => void;
    studioApi.createExplanationReproducibility.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectAnalysis = reject; }));
    renderEvidence();

    const checkboxes = await screen.findAllByRole("checkbox");
    for (const checkbox of checkboxes) fireEvent.click(checkbox);
    const compare = await screen.findByRole("button", { name: "Compare explanation reproducibility" });
    act(() => {
      compare.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      compare.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.createExplanationReproducibility).toHaveBeenCalledTimes(1);
    expect(studioApi.createExplanationReproducibility).toHaveBeenCalledWith("session", explanations.map((item) => item.explanation_id));
    await act(async () => { rejectAnalysis(new Error("analysis response unavailable")); });
    expect(await screen.findByTestId("reproducibility-recovery")).toHaveTextContent("analysis response unavailable");
  });

  it("submits one comparison for the selected persisted result pair", async () => {
    studioApi.listBehaviorResults.mockReset().mockResolvedValue([
      { result_id: "result-a", spec_id: "spec-1", status: "PASS" },
      { result_id: "result-b", spec_id: "spec-1", status: "FAIL" },
    ] as never);
    let rejectComparison!: (error: Error) => void;
    studioApi.compareBehaviorResults.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectComparison = reject; }));
    renderEvidence();

    const baseline = await screen.findByRole("combobox", { name: "Behavior baseline result" });
    const candidate = screen.getByRole("combobox", { name: "Behavior candidate result" });
    fireEvent.change(baseline, { target: { value: "result-a" } });
    fireEvent.change(candidate, { target: { value: "result-b" } });
    const compare = await screen.findByRole("button", { name: "Compare revisions" });
    await waitFor(() => expect(compare).toBeEnabled());
    act(() => {
      compare.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      compare.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.compareBehaviorResults).toHaveBeenCalledTimes(1);
    expect(studioApi.compareBehaviorResults).toHaveBeenCalledWith("session", "result-a", "result-b");
    await act(async () => { rejectComparison(new Error("comparison response unavailable")); });
    expect(await screen.findByTestId("behavior-comparison-recovery")).toHaveTextContent("comparison response unavailable");
  });

  it("creates a single BehaviorSpec when submit events arrive before React rerenders", async () => {
    let rejectCreate!: (error: Error) => void;
    studioApi.createBehaviorSpec.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectCreate = reject; }));
    renderEvidence();

    const create = await screen.findByRole("button", { name: "Create and run BehaviorSpec" });
    act(() => {
      create.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      create.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.createBehaviorSpec).toHaveBeenCalledTimes(1);
    expect(create).toBeDisabled();
    await act(async () => { rejectCreate(new Error("creation response unavailable")); });
    expect(await screen.findByTestId("behavior-spec-create-recovery")).toHaveTextContent("creation response unavailable");
    expect(studioApi.createBehaviorSpec).toHaveBeenCalledTimes(1);
    expect(studioApi.runBehaviorSpec).not.toHaveBeenCalled();
  });

  it("serializes condition-monitoring demo submission and retains its exact request after uncertainty", async () => {
    let rejectDemo!: (error: Error) => void;
    studioApi.runConditionMonitoringDemo.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectDemo = reject; }));
    renderEvidence(null, { policy_id: "frozen-policy" } as never);

    const runDemo = await screen.findByRole("button", { name: "Run telemetry demonstration" });
    await waitFor(() => expect(runDemo).toBeEnabled());
    act(() => {
      runDemo.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      runDemo.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.runConditionMonitoringDemo).toHaveBeenCalledTimes(1);
    expect(studioApi.runConditionMonitoringDemo).toHaveBeenCalledWith("session", { x: 0 }, "frozen-policy", null);
    expect(runDemo).toBeDisabled();
    await act(async () => { rejectDemo(new Error("demo response unavailable")); });
    expect(await screen.findByTestId("condition-demo-recovery")).toHaveTextContent("demo response unavailable");
    expect(studioApi.runConditionMonitoringDemo).toHaveBeenCalledTimes(1);
  });

  it("serializes AssuranceCase and VerificationBundle submissions across actions", async () => {
    studioApi.startAssuranceCaseJob.mockResolvedValueOnce({ job_id: "assurance-job", kind: "assurance_case", status: "failed", message: "Failed", error: "temporary failure", output: {} });
    renderEvidence({ gates: [], claims: [], unresolved_risks: [] } as never);

    const assurance = await screen.findByRole("button", { name: "Build AssuranceCase" });
    const bundle = screen.getByRole("button", { name: "Export and validate bundle" });
    act(() => {
      assurance.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      assurance.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      bundle.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.startAssuranceCaseJob).toHaveBeenCalledTimes(1);
    expect(studioApi.startVerificationBundleJob).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent("temporary failure");
  });

  it("serializes exact AssuranceCase job resume after an uncertain status read", async () => {
    const queuedJob = { job_id: "assurance-job", kind: "assurance_case", status: "queued", message: "Queued", error: null, output: {} };
    studioApi.startAssuranceCaseJob.mockResolvedValueOnce(queuedJob as never);
    studioApi.getPosthocExplanationJob.mockRejectedValue(new Error("temporary status read failure"));
    renderEvidence();

    const build = await screen.findByRole("button", { name: "Build AssuranceCase" });
    await act(async () => { build.click(); });
    const resume = await screen.findByRole("button", { name: "Resume saved evidence job" });
    await waitFor(() => expect(screen.getByTestId("evidence-operation-resume")).toHaveTextContent("temporary status read failure"));
    act(() => {
      resume.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      resume.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitFor(() => expect(studioApi.getPosthocExplanationJob).toHaveBeenCalledTimes(2));
    expect(studioApi.startAssuranceCaseJob).toHaveBeenCalledTimes(1);
  });

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

  it("allows queued-job cancellation during polling but submits cancellation only once", async () => {
    const queuedJob = { job_id: "job-cancel", kind: "explanation_generation", status: "queued", message: "Queued", error: null, output: {} };
    const cancelledJob = { ...queuedJob, status: "cancelled", message: "Cancellation requested" };
    let finishStatus!: (value: never) => void;
    let finishCancellation!: (value: never) => void;
    studioApi.startPosthocExplanationJob.mockResolvedValueOnce(queuedJob as never);
    studioApi.getPosthocExplanationJob.mockImplementationOnce(() => new Promise((resolve) => { finishStatus = resolve as (value: never) => void; }));
    studioApi.cancelEvidenceJob.mockImplementationOnce(() => new Promise((resolve) => { finishCancellation = resolve as (value: never) => void; }));
    renderEvidence();

    const generate = await screen.findByRole("button", { name: "Generate explanation" });
    await act(async () => { generate.click(); });
    await waitFor(() => expect(studioApi.getPosthocExplanationJob).toHaveBeenCalledTimes(1));
    const cancel = await screen.findByRole("button", { name: "Cancel queued job" });
    expect(cancel).toBeEnabled();
    act(() => {
      cancel.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      cancel.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.cancelEvidenceJob).toHaveBeenCalledTimes(1);
    expect(cancel).toBeDisabled();
    await act(async () => {
      finishCancellation(cancelledJob as never);
      finishStatus(cancelledJob as never);
    });
    await waitFor(() => expect(screen.getByTestId("explanation-job")).toHaveTextContent("CANCELLED"));
    expect(studioApi.cancelEvidenceJob).toHaveBeenCalledTimes(1);
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
