import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  listSplitContracts: vi.fn().mockResolvedValue([]),
  createSplitContract: vi.fn(),
  getSplitContract: vi.fn(),
  getTransformPipeline: vi.fn(),
  getLeakageAudit: vi.fn(),
  getModels: vi.fn().mockResolvedValue([
    {
      key: "flat_neuro_fuzzy", display_name: "Flat Neuro-Fuzzy", version: "1", provider: "builtin", family: "neuro_fuzzy",
      supported_tasks: ["binary_classification"], training_model_kinds: ["flat_neuro_fuzzy"], input_modalities: ["tabular"], available: true,
      unavailability_reason: null, capabilities: { fit: true }, supported_explainers: [], export_formats: [], config_schema: {},
      defaults: { max_epochs: 20, learning_rate: 0.01, batch_size: 32, patience: 8, max_rules: 8 },
      parameter_constraints: { max_epochs: {}, learning_rate: {}, batch_size: {}, patience: {}, max_rules: {} }, optional_dependencies: [], evidence_objects_produced: [], limitations: [],
    },
    {
      key: "random_forest", display_name: "Random Forest", version: "1", provider: "builtin", family: "tree_ensemble",
      supported_tasks: ["binary_classification"], training_model_kinds: ["random_forest"], input_modalities: ["tabular"], available: true,
      unavailability_reason: null, capabilities: { fit: true }, supported_explainers: [], export_formats: [], config_schema: {},
      defaults: { n_estimators: 25, max_depth: null }, parameter_constraints: { n_estimators: { minimum: 1 }, max_depth: { minimum: 1, nullable: true } }, optional_dependencies: [], evidence_objects_produced: [], limitations: [],
    },
  ]),
  getRuntimeBackends: vi.fn().mockResolvedValue([{ identity: { key: "local_executor", version: "1", provider: "ruflex.builtin", kind: "execution_backend" }, supports_cancel: true, supports_resume: true }]),
  listStudyJobs: vi.fn().mockResolvedValue([]),
  startStudyJob: vi.fn(),
  cancelStudyJob: vi.fn(),
  runTraining: vi.fn(),
  getTrainingRuns: vi.fn().mockResolvedValue([]),
  getStudyJob: vi.fn(),
  resumeStudyJob: vi.fn(),
  getLatestTrainingStudy: vi.fn(),
  getTrainingRunCapabilities: vi.fn().mockResolvedValue({ decisions: [] }),
  getLatestTreePath: vi.fn(),
} }));

vi.mock("../../api", async (importOriginal) => ({ ...await importOriginal<typeof import("../../api")>(), studioApi }));
vi.mock("../../components/StudioPrimitives", () => ({
  Button: ({ children, view: _view, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { view?: string }) => <button {...props}>{children}</button>,
  EmptyState: ({ title, children }: { title: string; children: React.ReactNode }) => <div><strong>{title}</strong>{children}</div>,
  StatusBadge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("../../charts/ChartSurface", () => ({ ChartSurface: () => <div /> }));
vi.mock("./StabilityLab", () => ({ StabilityLab: () => <div /> }));

import { ExperimentWorkspace } from "./ExperimentWorkspace";
import { ProductApiError } from "../../api";

const project = { session_id: "session", project_id: "project", name: "Test", description: null, root: "/tmp/test", schema_version: 1, read_only: false, modified_at: "2026-01-01T00:00:00Z" };
const dataset = {
  contract: { target: "target", task: "binary_classification", feature_columns: ["x"], id_columns: [], dataset_fingerprint: "fingerprint", source_artifact_sha256: "a".repeat(64), source_format: "csv", row_identity_scheme: "row", role_decisions: { x: "feature", target: "target" } },
  profile: { row_count: 10, id_candidates: [], columns: [{ name: "x" }, { name: "target" }] },
  preview: [], audit: { findings: [] },
};

beforeEach(() => {
  studioApi.listSplitContracts.mockResolvedValue([]);
  studioApi.createSplitContract.mockReset();
  studioApi.getSplitContract.mockReset();
  studioApi.getTransformPipeline.mockReset();
  studioApi.getLeakageAudit.mockReset();
  studioApi.getTrainingRunCapabilities.mockResolvedValue({ decisions: [] });
  studioApi.getLatestTreePath.mockResolvedValue({ run_id: "other-run" });
  studioApi.getStudyJob.mockReset();
  studioApi.resumeStudyJob.mockReset();
  studioApi.getLatestTrainingStudy.mockReset();
  studioApi.startStudyJob.mockReset();
  studioApi.cancelStudyJob.mockReset();
  studioApi.runTraining.mockReset();
  studioApi.getTrainingRuns.mockReset();
  studioApi.getTrainingRuns.mockResolvedValue([]);
});

describe("ExperimentWorkspace dynamic model controls", () => {
  it("synchronously rejects duplicate SplitContract writes before React can rerender", async () => {
    const frozenSplit = {
      split_id: "split-once", dataset_fingerprint: "fingerprint", dataset_artifact_sha256: "a".repeat(64),
      family: "RANDOM", split_seed: 42, validation_fraction: 0.2, test_fraction: 0.2,
      group_column: null, time_column: null, site_column: null, device_column: null, spatial_column: null, regime_column: null,
    };
    let finishSplit!: (value: never) => void;
    studioApi.createSplitContract.mockImplementationOnce(() => new Promise((resolve) => { finishSplit = resolve as (value: never) => void; }));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const freezeButton = await screen.findByRole("button", { name: "Freeze RANDOM SplitContract" });
    await waitFor(() => expect(freezeButton).toBeEnabled());
    act(() => {
      freezeButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      freezeButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(studioApi.createSplitContract).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Freezing split…" })).toBeDisabled();
    expect(screen.getByText("Saving split contract")).toBeVisible();
    await act(async () => { finishSplit(frozenSplit as never); });
    await waitFor(() => expect(screen.getByText(/RANDOM · split-on/)).toBeVisible());
    expect(studioApi.createSplitContract).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "SplitContract frozen" })).toBeDisabled();
  });

  it("keeps split validation errors editable instead of treating them as uncertain writes", async () => {
    studioApi.createSplitContract
      .mockRejectedValueOnce(new ProductApiError({ code: "VALIDATION_FAILED", status: 422, detail: "GROUP split requires at least three distinct groups." }))
      .mockResolvedValueOnce({
        split_id: "split-random", dataset_fingerprint: "fingerprint", dataset_artifact_sha256: "a".repeat(64),
        family: "RANDOM", split_seed: 42, validation_fraction: 0.2, test_fraction: 0.2,
        group_column: null, time_column: null, site_column: null, device_column: null, spatial_column: null, regime_column: null,
      } as never);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByRole("option", { name: "Random Forest" });
    fireEvent.change(screen.getByLabelText("Split family"), { target: { value: "GROUP" } });
    fireEvent.change(screen.getByLabelText("Split identity column"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Freeze GROUP SplitContract" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("GROUP split requires at least three distinct groups.");
    expect(screen.queryByTestId("split-contract-recovery")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Split family"), { target: { value: "RANDOM" } });
    fireEvent.click(screen.getByRole("button", { name: "Freeze RANDOM SplitContract" }));
    await waitFor(() => expect(studioApi.createSplitContract).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("split-contract-recovery")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run real training" })).toBeEnabled();
  });

  it("blocks fitting when visible split settings no longer match the frozen contract", async () => {
    studioApi.listSplitContracts.mockResolvedValueOnce([{
      split_id: "split-group", dataset_fingerprint: "fingerprint", dataset_artifact_sha256: "a".repeat(64),
      family: "GROUP", split_seed: 7, validation_fraction: 0.25, test_fraction: 0.25,
      group_column: "x", time_column: null, site_column: null, device_column: null, spatial_column: null, regime_column: null,
    }]);
    studioApi.runTraining.mockResolvedValueOnce({} as never);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const runButton = await screen.findByRole("button", { name: "Run real training" });
    await waitFor(() => expect(runButton).toBeEnabled());
    expect(screen.getByText("50% train · 25% validation · 25% locked test")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Split family"), { target: { value: "RANDOM" } });
    expect(runButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Split family"), { target: { value: "GROUP" } });
    fireEvent.change(screen.getByLabelText("Study split seed"), { target: { value: "8" } });
    expect(runButton).toBeDisabled();
    expect(screen.getByText(/no legacy RANDOM fallback will be used/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
    expect(studioApi.runTraining).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Study split seed"), { target: { value: "7" } });
    await waitFor(() => expect(runButton).toBeEnabled());
    fireEvent.click(runButton);
    await waitFor(() => expect(studioApi.runTraining).toHaveBeenCalledTimes(1));
    expect(studioApi.runTraining.mock.calls[0][1].validation_fraction).toBe(0.25);
    expect(studioApi.runTraining.mock.calls[0][1].test_fraction).toBe(0.25);
  });

  it("keeps single-run training validation errors editable and reserves recovery for uncertain writes", async () => {
    studioApi.runTraining.mockRejectedValueOnce(new ProductApiError({ code: "VALIDATION_FAILED", status: 422, detail: "Configured estimator parameter is invalid." }));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const runButton = await screen.findByRole("button", { name: "Run real training" });
    await waitFor(() => expect(runButton).toBeEnabled());
    fireEvent.click(runButton);

    expect(await screen.findByRole("alert")).toHaveTextContent("Configured estimator parameter is invalid.");
    expect(screen.queryByTestId("training-run-recovery")).not.toBeInTheDocument();
    expect(runButton).toBeEnabled();
  });

  it("does not offer explicit single-fit retry while a restored StudyJob is active", async () => {
    const activeJob = {
      job_id: "job-running", name: "Active Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "RUNNING", cancel_requested: false, seed_states: [{ seed: 3, status: "RUNNING", run_id: null, runtime_seconds: null, error: null }],
      study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    };
    studioApi.runTraining.mockRejectedValueOnce(new Error("training response lost"));
    studioApi.listStudyJobs.mockResolvedValueOnce([]).mockResolvedValueOnce([activeJob]);
    studioApi.getTrainingRuns.mockResolvedValueOnce([]);
    const view = render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const runButton = await screen.findByRole("button", { name: "Run real training" });
    await waitFor(() => expect(runButton).toBeEnabled());
    fireEvent.click(runButton);
    expect(await screen.findByTestId("training-run-recovery")).toBeVisible();

    view.rerender(<ExperimentWorkspace project={{ ...project, session_id: "session-reopened" }} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);
    await screen.findByText(/Study job RUNNING/);
    fireEvent.click(screen.getByRole("button", { name: "Retry exact TrainingRun lookup" }));
    const explicitRetry = await screen.findByRole("button", { name: "Explicitly start a new fit with these settings" });
    await waitFor(() => expect(explicitRetry).toBeDisabled());
    fireEvent.click(explicitRetry);
    expect(studioApi.runTraining).toHaveBeenCalledTimes(1);
  });

  it("synchronously rejects duplicate single-run submissions before React can rerender", async () => {
    let finishRun!: (value: never) => void;
    studioApi.runTraining.mockImplementationOnce(() => new Promise((resolve) => { finishRun = resolve as (value: never) => void; }));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const runButton = await screen.findByRole("button", { name: "Run real training" });
    await waitFor(() => expect(runButton).toBeEnabled());
    act(() => {
      runButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      runButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(studioApi.runTraining).toHaveBeenCalledTimes(1);
    expect(runButton).toBeDisabled();
    await act(async () => { finishRun({} as never); });
    await waitFor(() => expect(runButton).toBeEnabled());
    expect(studioApi.runTraining).toHaveBeenCalledTimes(1);
  });

  it("synchronously rejects duplicate Study submissions before React can rerender", async () => {
    const completed = { job_id: "job-study-once", name: "Study", model_kind: "flat_neuro_fuzzy", selection_metric: "f1", status: "SUCCEEDED", cancel_requested: false, seed_states: [], study_id: "study-once", error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null };
    let finishStudy!: (value: never) => void;
    studioApi.startStudyJob.mockImplementationOnce(() => new Promise((resolve) => { finishStudy = resolve as (value: never) => void; }));
    studioApi.getLatestTrainingStudy.mockResolvedValue({ study_id: "study-once", selection_metric: "f1", selected_run_id: null, seed_runs: [] });
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const start = await screen.findByRole("button", { name: "Run multi-seed study" });
    await waitFor(() => expect(start).toBeEnabled());
    act(() => {
      start.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      start.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.startStudyJob).toHaveBeenCalledTimes(1);
    expect(start).toBeDisabled();
    await act(async () => { finishStudy(completed as never); });
    await waitFor(() => expect(screen.getByText(/Study job SUCCEEDED/)).toBeVisible());
    expect(studioApi.startStudyJob).toHaveBeenCalledTimes(1);
  });

  it("clears a rejected Study request so corrected parameters create a new request", async () => {
    studioApi.startStudyJob
      .mockRejectedValueOnce(new ProductApiError({ code: "VALIDATION_FAILED", status: 422, detail: "Study configuration is invalid." }))
      .mockRejectedValueOnce(new ProductApiError({ code: "VALIDATION_FAILED", status: 422, detail: "Study configuration is invalid." }));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const studyButton = await screen.findByRole("button", { name: "Run multi-seed study" });
    await waitFor(() => expect(studyButton).toBeEnabled());
    fireEvent.click(studyButton);
    expect(await screen.findByRole("alert")).toHaveTextContent("Study configuration is invalid.");
    expect(screen.queryByText(/Retry uses the same request ID/)).not.toBeInTheDocument();
    expect(studyButton).toBeEnabled();

    fireEvent.change(screen.getByLabelText("Learning rate"), { target: { value: "0.02" } });
    fireEvent.click(studyButton);
    await waitFor(() => expect(studioApi.startStudyJob).toHaveBeenCalledTimes(2));
    expect(studioApi.startStudyJob.mock.calls[1][1].client_request_id).not.toBe(studioApi.startStudyJob.mock.calls[0][1].client_request_id);
    expect(studioApi.startStudyJob.mock.calls[1][1].learning_rate).toBe(0.02);
  });

  it("retries an uncertain Study submission with the exact same request identity and configuration", async () => {
    studioApi.startStudyJob.mockRejectedValueOnce(new Error("response lost after submit"));
    studioApi.startStudyJob.mockRejectedValueOnce(new ProductApiError({ code: "VALIDATION_FAILED", status: 422, detail: { code: "RUNTIME_INCOMPATIBLE", message: "Selected runtime cannot execute this request." } }));
    const completed = { job_id: "job-1", name: "Study", model_kind: "flat_neuro_fuzzy", selection_metric: "f1", status: "SUCCEEDED", cancel_requested: false, seed_states: [], study_id: "study-1", error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null };
    studioApi.startStudyJob.mockResolvedValueOnce(completed);
    studioApi.getLatestTrainingStudy.mockResolvedValue({ study_id: "study-1", selection_metric: "f1", selected_run_id: null, seed_runs: [] });
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const start = await screen.findByRole("button", { name: "Run multi-seed study" });
    await waitFor(() => expect(start).toBeEnabled());
    fireEvent.click(start);
    expect(await screen.findByRole("status")).toHaveTextContent("Retry uses the same request ID");
    fireEvent.click(screen.getByRole("button", { name: "Retry same Study request" }));
    await waitFor(() => expect(studioApi.startStudyJob).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("alert")).toHaveTextContent("Selected runtime cannot execute this request.");
    fireEvent.click(screen.getByRole("button", { name: "Retry same Study request" }));
    await waitFor(() => expect(studioApi.startStudyJob).toHaveBeenCalledTimes(3));
    expect(studioApi.startStudyJob.mock.calls[1]).toEqual(studioApi.startStudyJob.mock.calls[0]);
    expect(studioApi.startStudyJob.mock.calls[2]).toEqual(studioApi.startStudyJob.mock.calls[0]);
    expect(studioApi.startStudyJob.mock.calls[0][1].client_request_id).toMatch(/^[0-9a-f-]{36}$/i);
  });

  it("explains that a cancelled StudyJob is terminal and its completed fits are retained", async () => {
    studioApi.listStudyJobs.mockResolvedValueOnce([{
      job_id: "job-cancelled", name: "Interrupted Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "CANCELLED", cancel_requested: true, seed_states: [{ seed: 3, status: "SUCCEEDED", run_id: "run-3", runtime_seconds: 1, error: null }],
      study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    }]);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(await screen.findByText(/This StudyJob is terminal and cannot be resumed/)).toBeVisible();
    expect(screen.getByText(/Seed fits completed before cancellation remain persisted/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Resume persisted study" })).not.toBeInTheDocument();
  });

  it("blocks a second Study submission while a persisted StudyJob is active", async () => {
    studioApi.listStudyJobs.mockResolvedValueOnce([{
      job_id: "job-running", name: "Active Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "RUNNING", cancel_requested: false, seed_states: [{ seed: 3, status: "RUNNING", run_id: null, runtime_seconds: null, error: null }],
      study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    }]);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByText(/Study job RUNNING/);
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
    expect(studioApi.startStudyJob).not.toHaveBeenCalled();
  });

  it("blocks single-run fitting while a persisted StudyJob is active", async () => {
    studioApi.listStudyJobs.mockResolvedValueOnce([{
      job_id: "job-running", name: "Active Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "RUNNING", cancel_requested: false, seed_states: [{ seed: 3, status: "RUNNING", run_id: null, runtime_seconds: null, error: null }],
      study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    }]);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByText(/Study job RUNNING/);
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(studioApi.runTraining).not.toHaveBeenCalled();
  });

  it("keeps single-run fitting disabled when persisted StudyJob status cannot be restored", async () => {
    studioApi.listStudyJobs.mockRejectedValueOnce(new Error("job store unavailable"));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByText("Could not restore saved Study jobs.", { exact: true });
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(studioApi.runTraining).not.toHaveBeenCalled();
  });

  it("shows accepted cancellation in progress without offering invalid resume or duplicate cancel actions", async () => {
    studioApi.listStudyJobs.mockResolvedValueOnce([{
      job_id: "job-cancel-requested", name: "Cancelling Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "RUNNING", cancel_requested: true, seed_states: [{ seed: 3, status: "RUNNING", run_id: null, runtime_seconds: null, error: null }],
      study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    }]);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(await screen.findByText(/Cancellation requested\. The active seed fit may finish/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Resume persisted study" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel study" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
  });

  it("synchronously sends one cancellation request for a persisted StudyJob", async () => {
    const job = {
      job_id: "job-cancel-once", name: "Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "RUNNING", cancel_requested: false, seed_states: [{ seed: 3, status: "RUNNING", run_id: null, runtime_seconds: null, error: null }],
      study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    };
    let finishCancel!: (value: never) => void;
    studioApi.listStudyJobs.mockResolvedValueOnce([job]);
    studioApi.cancelStudyJob.mockImplementationOnce(() => new Promise((resolve) => { finishCancel = resolve as (value: never) => void; }));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const cancel = await screen.findByRole("button", { name: "Cancel study" });
    act(() => {
      cancel.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      cancel.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.cancelStudyJob).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Requesting cancellation…" })).toBeDisabled();
    await act(async () => { finishCancel({ ...job, cancel_requested: true } as never); });
    expect(await screen.findByText(/Cancellation requested\. The active seed fit may finish/)).toBeVisible();
    expect(studioApi.cancelStudyJob).toHaveBeenCalledTimes(1);
  });

  it("shows the persisted StudyJob and per-seed failure reasons", async () => {
    studioApi.listStudyJobs.mockResolvedValueOnce([{
      job_id: "job-failed", name: "Failed Study", model_kind: "logistic_regression", selection_metric: "f1",
      status: "FAILED", cancel_requested: false, seed_states: [{ seed: 9, status: "FAILED", run_id: null, runtime_seconds: null, error: "adapter runtime unavailable" }],
      study_id: null, error: "Fewer than three seed runs succeeded; no scientific selection was produced.", execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null,
    }]);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(await screen.findByText(/StudyJob error: Fewer than three seed runs succeeded/)).toBeVisible();
    expect(screen.getByText("Seed 9: adapter runtime unavailable")).toBeVisible();
  });

  it("does not hide exact tree-path support when the saved capability check fails and retries the same run", async () => {
    studioApi.getTrainingRunCapabilities
      .mockRejectedValueOnce(new Error("run capability store unavailable"))
      .mockResolvedValueOnce({ run_id: "tree-run", decisions: [{ capability: "exact_tree_path", status: "AVAILABLE" }] });
    const run = {
      run_id: "tree-run", model_kind: "decision_tree", trajectory: [], training_summary: { best_epoch: 1, epochs_ran: 1, monitor_name: "loss", best_monitor_value: 0.1 },
      feature_columns: ["x"], model_artifact_sha256: "a".repeat(64), split: { train_count: 4, validation_count: 2, test_count: 2 }, seed: 3,
    };
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={run as never} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("run capability store unavailable");
    expect(screen.queryByRole("button", { name: "Trace exact tree path" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry run capability check" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Trace exact tree path" })).toBeEnabled());
    expect(studioApi.getTrainingRunCapabilities).toHaveBeenNthCalledWith(1, "session", "tree-run");
    expect(studioApi.getTrainingRunCapabilities).toHaveBeenNthCalledWith(2, "session", "tree-run");
  });

  it("distinguishes unavailable saved tree-path evidence from absence and retries the same lookup", async () => {
    const evidence = { evidence_id: "tree-evidence", run_id: "tree-run", model_artifact_sha256: "a".repeat(64), preprocessing_identity: "prep", input_sample: { x: 1 }, steps: [], leaf_id: 2, prediction: 1, class_probabilities: { "1": 1 }, label: "EXACT TREE EXECUTION PATH" };
    studioApi.getTrainingRunCapabilities.mockResolvedValue({ run_id: "tree-run", decisions: [{ capability: "exact_tree_path", status: "AVAILABLE" }] });
    studioApi.getLatestTreePath.mockRejectedValueOnce(new Error("tree path store temporarily unavailable")).mockResolvedValueOnce(evidence);
    const run = {
      run_id: "tree-run", model_kind: "decision_tree", trajectory: [], training_summary: { best_epoch: 1, epochs_ran: 1, monitor_name: "loss", best_monitor_value: 0.1 },
      feature_columns: ["x"], model_artifact_sha256: "a".repeat(64), split: { train_count: 4, validation_count: 2, test_count: 2 }, seed: 3,
    };
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={run as never} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("tree path store temporarily unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry tree-path check" }));
    await waitFor(() => expect(screen.getByText("EXACT TREE EXECUTION PATH", { exact: true })).toBeVisible());
    expect(studioApi.getLatestTreePath).toHaveBeenCalledTimes(2);
    expect(studioApi.getLatestTreePath).toHaveBeenNthCalledWith(1, "session");
    expect(studioApi.getLatestTreePath).toHaveBeenNthCalledWith(2, "session");
  });

  it("does not report an empty dataset when persisted dataset hydration failed", () => {
    const retry = vi.fn();
    render(<ExperimentWorkspace project={project} dataset={null} datasetHydrationStatus="error" datasetHydrationError="dataset store unavailable" onRetryDatasetHydration={retry} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not restore the persisted DatasetContract");
    expect(screen.getByRole("alert")).toHaveTextContent("dataset store unavailable");
    expect(screen.queryByText("No confirmed dataset")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry dataset check" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("retries the same persisted StudyJob after a transient status-poll failure", async () => {
    const job = { job_id: "job-123", name: "Study", model_kind: "flat_neuro_fuzzy", selection_metric: "f1", status: "RUNNING", cancel_requested: false, seed_states: [], study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", recovery_note: null };
    studioApi.listStudyJobs.mockResolvedValueOnce([job]);
    studioApi.resumeStudyJob.mockResolvedValue(job);
    studioApi.getStudyJob.mockRejectedValueOnce(new Error("job status store unavailable"));
    studioApi.getStudyJob.mockResolvedValueOnce({ ...job, status: "SUCCEEDED", study_id: "study-123" });
    studioApi.getLatestTrainingStudy.mockResolvedValue({ study_id: "study-123", selection_metric: "f1", selected_run_id: "selected", seed_runs: [] });
    const onStudy = vi.fn();
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={onStudy} />);

    const resume = await screen.findByRole("button", { name: "Resume persisted study" });
    fireEvent.click(resume);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Study status could not be refreshed"));
    expect(studioApi.getStudyJob).toHaveBeenNthCalledWith(1, "session", "job-123");
    fireEvent.click(screen.getByRole("button", { name: "Retry Study status" }));
    await waitFor(() => expect(screen.getByText(/Study job SUCCEEDED/)).toBeVisible());
    expect(studioApi.getStudyJob).toHaveBeenNthCalledWith(2, "session", "job-123");
    expect(onStudy).toHaveBeenCalledOnce();
  });

  it("synchronously rejects duplicate resume requests for one persisted StudyJob", async () => {
    const job = { job_id: "job-resume-once", name: "Study", model_kind: "flat_neuro_fuzzy", selection_metric: "f1", status: "RUNNING", cancel_requested: false, seed_states: [], study_id: null, error: null, execution_backend: "LOCAL", execution_backend_key: "local_executor", execution_config: {}, recovery_count: 0, recovery_note: null };
    const completed = { ...job, status: "SUCCEEDED", study_id: "study-resumed" };
    let finishResume!: (value: never) => void;
    studioApi.listStudyJobs.mockResolvedValueOnce([job]);
    studioApi.resumeStudyJob.mockImplementationOnce(() => new Promise((resolve) => { finishResume = resolve as (value: never) => void; }));
    studioApi.getLatestTrainingStudy.mockResolvedValue({ study_id: "study-resumed", selection_metric: "f1", selected_run_id: null, seed_runs: [] });
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const resume = await screen.findByRole("button", { name: "Resume persisted study" });
    act(() => {
      resume.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      resume.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(studioApi.resumeStudyJob).toHaveBeenCalledTimes(1);
    expect(resume).toBeDisabled();
    await act(async () => { finishResume(completed as never); });
    await waitFor(() => expect(screen.getByText(/Study job SUCCEEDED/)).toBeVisible());
    expect(studioApi.resumeStudyJob).toHaveBeenCalledTimes(1);
  });

  it("keeps Study creation paused while saved Study and job lookups are unresolved, then retries", async () => {
    studioApi.listStudyJobs.mockRejectedValueOnce(new Error("job store unavailable"));
    const retryStudy = vi.fn();
    const view = render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} studyHydrationStatus="error" studyHydrationError="study store unavailable" onRetryStudyHydration={retryStudy} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not restore saved TrainingStudy");
    expect(screen.getByRole("alert")).toHaveTextContent("study store unavailable");
    const startStudy = screen.getByRole("button", { name: "Run multi-seed study" });
    expect(startStudy).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry Study check" }));
    expect(retryStudy).toHaveBeenCalledOnce();
    view.rerender(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} studyHydrationStatus="none" onRetryStudyHydration={retryStudy} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Could not restore saved Study jobs.", { exact: true })).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "Retry Study jobs" }));
    await waitFor(() => expect(startStudy).toBeEnabled());
  });

  it("shows only the selected adapter's declared parameters", async () => {
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByRole("option", { name: "Flat Neuro-Fuzzy" });
    expect(screen.getByLabelText("Study execution backend")).toHaveValue("local_executor");
    expect(screen.getByLabelText("Epochs")).toBeVisible();
    expect(screen.getByLabelText("Max rules / layer")).toBeVisible();
    expect(screen.queryByLabelText("Trees / estimators")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Training model"), { target: { value: "random_forest" } });
    await waitFor(() => expect(screen.getByLabelText("Trees / estimators")).toBeVisible());
    expect(screen.queryByLabelText("Epochs")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Max rules / layer")).not.toBeInTheDocument();
  });

  it("rejects ambiguous Study seed lists before submission and recovers when corrected", async () => {
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    const seeds = screen.getByLabelText("Study seeds");
    const startStudy = screen.getByRole("button", { name: "Run multi-seed study" });
    await waitFor(() => expect(startStudy).toBeEnabled());
    fireEvent.change(seeds, { target: { value: "42, nope, 44, 45" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid entries are not ignored");
    expect(seeds).toHaveAttribute("aria-invalid", "true");
    expect(startStudy).toBeDisabled();

    fireEvent.change(seeds, { target: { value: "42, 43, 44" } });
    await waitFor(() => expect(startStudy).toBeEnabled());
    expect(seeds).toHaveAttribute("aria-invalid", "false");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    fireEvent.change(seeds, { target: { value: "42, 43, 43" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Each Study seed must be distinct");
    expect(startStudy).toBeDisabled();
  });

  it("applies adapter and API numeric bounds before either training action is enabled", async () => {
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByRole("option", { name: "Random Forest" });
    fireEvent.change(screen.getByLabelText("Training model"), { target: { value: "random_forest" } });
    const singleRun = screen.getByRole("button", { name: "Run real training" });
    const study = screen.getByRole("button", { name: "Run multi-seed study" });

    fireEvent.change(await screen.findByLabelText("Trees / estimators"), { target: { value: "5001" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Trees / estimators must be at most 5000");
    expect(screen.getByLabelText("Trees / estimators")).toHaveAttribute("max", "5000");
    expect(singleRun).toBeDisabled();
    expect(study).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Trees / estimators"), { target: { value: "5000" } });
    await waitFor(() => expect(singleRun).toBeEnabled());
    expect(study).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reopens and presents persisted split, train-only transform and leakage-audit evidence", async () => {
    const split = {
      split_id: "split-12345678", family: "GROUP", split_seed: 7, group_column: "patient_id", time_column: null,
      site_column: null, device_column: null, spatial_column: null, regime_column: null,
      role_source_rows: { train: [0, 1, 2, 3], validation: [4, 5], test: [6, 7] },
      split_identity: "split-identity-sha", dataset_fingerprint: "fingerprint", dataset_artifact_sha256: "a".repeat(64),
      validation_fraction: 0.25, test_fraction: 0.25, role_identity_hashes: { train: "t", validation: "v", test: "x" }, scientific_note: "membership only",
    };
    studioApi.listSplitContracts.mockResolvedValue([split]);
    studioApi.getTransformPipeline.mockResolvedValue({
      pipeline_id: "pipeline-1", dataset_fingerprint: "fingerprint", split_contract_id: split.split_id,
      feature_order: ["x"], fit_role: "TRAIN", preprocessing_artifact_sha256: "b".repeat(64), pipeline_identity: "identity",
      steps: [{ step_type: "MedianImputer", fit_role: "TRAIN", input_columns: ["x"], output_columns: ["x"], parameters: {}, artifact_identity: "b".repeat(64), version: "1" }],
      schema_version: 1, scientific_note: "TRAIN only",
    });
    studioApi.getSplitContract.mockResolvedValue(split);
    studioApi.getLeakageAudit.mockResolvedValue({
      audit_id: "audit-1", dataset_fingerprint: "fingerprint", split_contract_id: split.split_id,
      transform_pipeline_id: "pipeline-1", status: "WARN", rigor_profile: "CONFIRMATORY",
      findings: [{ code: "TARGET_DERIVED_FEATURE", severity: "warning", scope: "feature", evidence: { feature: "x" }, remediation: "Review this feature.", check_version: "1" }],
      schema_version: 1, scientific_note: "Declared checks only.",
    });
    const run = {
      run_id: "run-1", model_kind: "logistic_regression", trajectory: [], training_summary: { best_epoch: 1, epochs_ran: 1, monitor_name: "loss", best_monitor_value: 0.1 },
      model_artifact_sha256: "c".repeat(64), preprocessing_artifact_sha256: "b".repeat(64), transform_pipeline_id: "pipeline-1", leakage_audit_id: "audit-1",
      feature_columns: ["x"], split: { split_contract_id: split.split_id, train_count: 4, validation_count: 2, test_count: 2 }, seed: 7, model_spec: {},
    };
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={run as never} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    fireEvent.click(screen.getByText("Data governance evidence"));
    expect(await screen.findByText("GROUP · seed 7")).toBeVisible();
    expect(screen.getByText("Train 4 · validation 2 · locked test 2")).toBeVisible();
    expect(screen.getByText("TRAIN only · 1 persisted step(s)")).toBeVisible();
    expect(screen.getByText("WARNING · TARGET_DERIVED_FEATURE")).toBeVisible();
    expect(studioApi.getTransformPipeline).toHaveBeenCalledWith("session", "pipeline-1");
    expect(studioApi.getLeakageAudit).toHaveBeenCalledWith("session", "audit-1");
    expect(studioApi.getSplitContract).toHaveBeenCalledWith("session", split.split_id);
  });

  it("keeps linked run provenance unverified after a transient read error and retries the exact evidence", async () => {
    const run = {
      run_id: "run-retry", model_kind: "logistic_regression", trajectory: [], training_summary: { best_epoch: 1, epochs_ran: 1, monitor_name: "loss", best_monitor_value: 0.1 },
      model_artifact_sha256: "c".repeat(64), transform_pipeline_id: "pipeline-retry", leakage_audit_id: "audit-retry",
      feature_columns: ["x"], split: { split_contract_id: null, train_count: 4, validation_count: 2, test_count: 2 }, seed: 7, model_spec: {},
    };
    studioApi.getTransformPipeline
      .mockRejectedValueOnce(new Error("pipeline store temporarily unavailable"))
      .mockResolvedValueOnce({ pipeline_id: "pipeline-retry", dataset_fingerprint: "fingerprint", split_contract_id: null, feature_order: ["x"], fit_role: "TRAIN", preprocessing_artifact_sha256: "b".repeat(64), pipeline_identity: "pipeline-identity", steps: [], schema_version: 1, scientific_note: "TRAIN only" });
    studioApi.getLeakageAudit.mockResolvedValue({ audit_id: "audit-retry", dataset_fingerprint: "fingerprint", split_contract_id: null, transform_pipeline_id: "pipeline-retry", status: "PASS", rigor_profile: "CONFIRMATORY", findings: [], schema_version: 1, scientific_note: "Declared checks only." });
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={run as never} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    fireEvent.click(screen.getByText("Data governance evidence"));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("pipeline store temporarily unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry data evidence" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(studioApi.getTransformPipeline).toHaveBeenCalledTimes(2);
    expect(studioApi.getTransformPipeline).toHaveBeenLastCalledWith("session", "pipeline-retry");
    expect(studioApi.getLeakageAudit).toHaveBeenCalledWith("session", "audit-retry");
  });

  it("keeps runtime selection visible but blocks mutating training actions in read-only mode", async () => {
    render(<ExperimentWorkspace project={{ ...project, read_only: true }} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByRole("option", { name: "Random Forest" });
    expect(screen.getByText("Read-only projects cannot start training runs.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Freeze RANDOM SplitContract/ })).toBeDisabled();
  });

  it("blocks new fitting when saved split provenance cannot be verified", async () => {
    studioApi.listSplitContracts.mockRejectedValueOnce(new Error("Persisted SplitContract is malformed")).mockResolvedValueOnce([]);
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Training is blocked rather than falling back to an unverified split");
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry saved split check" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Run real training" })).toBeEnabled());
    expect(studioApi.listSplitContracts).toHaveBeenCalledTimes(2);
  });
});
