import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes } from "react";

const { studioApi } = vi.hoisted(() => ({ studioApi: {
  listSplitContracts: vi.fn().mockResolvedValue([]),
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
      defaults: { n_estimators: 25, max_depth: null }, parameter_constraints: { n_estimators: {}, max_depth: {} }, optional_dependencies: [], evidence_objects_produced: [], limitations: [],
    },
  ]),
  getRuntimeBackends: vi.fn().mockResolvedValue([{ identity: { key: "local_executor", version: "1", provider: "ruflex.builtin", kind: "execution_backend" }, supports_cancel: true, supports_resume: true }]),
  listStudyJobs: vi.fn().mockResolvedValue([]),
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

describe("ExperimentWorkspace dynamic model controls", () => {
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

  it("keeps runtime selection visible but blocks mutating training actions in read-only mode", async () => {
    render(<ExperimentWorkspace project={{ ...project, read_only: true }} dataset={dataset as never} run={null} study={null} theme={"light" as never} onRun={vi.fn()} onStudy={vi.fn()} />);

    await screen.findByRole("option", { name: "Random Forest" });
    expect(screen.getByText("Read-only projects cannot start training runs.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run real training" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run multi-seed study" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Freeze RANDOM SplitContract/ })).toBeDisabled();
  });
});
