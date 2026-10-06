import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  listSplitContracts: vi.fn().mockResolvedValue([]),
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
  getStudyJob: vi.fn(),
  resumeStudyJob: vi.fn(),
  getLatestTrainingStudy: vi.fn(),
  getTrainingRunCapabilities: vi.fn().mockResolvedValue({ decisions: [] }),
  getLatestTreePath: vi.fn(),
} }));

vi.mock("../../api", () => ({ studioApi }));
vi.mock("../../components/StudioPrimitives", () => ({
  Button: ({ children, view: _view, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { view?: string }) => <button {...props}>{children}</button>,
  EmptyState: ({ title, children }: { title: string; children: React.ReactNode }) => <div><strong>{title}</strong>{children}</div>,
  StatusBadge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));
vi.mock("../../charts/ChartSurface", () => ({ ChartSurface: () => <div /> }));
vi.mock("./StabilityLab", () => ({ StabilityLab: () => <div /> }));

import { ExperimentWorkspace } from "./ExperimentWorkspace";

const project = { session_id: "session", project_id: "project", name: "Test", description: null, root: "/tmp/test", schema_version: 1, read_only: false, modified_at: "2026-01-01T00:00:00Z" };
const dataset = {
  contract: { target: "target", task: "binary_classification", feature_columns: ["x"], id_columns: [], dataset_fingerprint: "fingerprint", source_artifact_sha256: "a".repeat(64), source_format: "csv", row_identity_scheme: "row", role_decisions: { x: "feature", target: "target" } },
  profile: { row_count: 10, id_candidates: [], columns: [{ name: "x" }, { name: "target" }] },
  preview: [], audit: { findings: [] },
};

beforeEach(() => {
  studioApi.listSplitContracts.mockResolvedValue([]);
  studioApi.getSplitContract.mockReset();
  studioApi.getTransformPipeline.mockReset();
  studioApi.getLeakageAudit.mockReset();
  studioApi.getTrainingRunCapabilities.mockResolvedValue({ decisions: [] });
  studioApi.getStudyJob.mockReset();
  studioApi.resumeStudyJob.mockReset();
  studioApi.getLatestTrainingStudy.mockReset();
});

describe("ExperimentWorkspace dynamic model controls", () => {
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

  it("keeps runtime selection visible but blocks mutating training actions in read-only mode", async () => {
    render(<ExperimentWorkspace project={{ ...project, read_only: true }} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByRole("option", { name: "Random Forest" });
    expect(screen.getByText("Read-only projects cannot start training runs.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Freeze RANDOM SplitContract/ })).toBeDisabled();
  });

  it("blocks new fitting when saved split provenance cannot be verified", async () => {
    studioApi.listSplitContracts.mockRejectedValue(new Error("Persisted SplitContract is malformed"));
    render(<ExperimentWorkspace project={project} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Training is blocked rather than falling back to an unverified split");
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
  });
});
