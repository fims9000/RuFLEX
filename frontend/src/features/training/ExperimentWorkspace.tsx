import { EChartsOption } from "echarts";
import { useEffect, useMemo, useRef, useState } from "react";
import { DatasetState, ExecutionBackendDescriptor, LeakageAuditReport, ModelCapabilityContract, ProductApiError, ProjectSummary, RunCapabilityNegotiation, SplitContract, StudyJob, StabilityGatePolicy, StudyStabilityAnalysis, TrainingRun, TrainingStudy, TransformPipelineContract, TreePathEvidence, studioApi } from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { Button, EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";
import { StabilityLab } from "./StabilityLab";
import { trainingRunMatchesRecovery } from "./trainingRecovery";

function trajectoryOption(run: TrainingRun): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["train loss", "validation loss"] },
    grid: { left: 54, right: 18, top: 38, bottom: 34 },
    xAxis: { type: "value", name: "epoch", minInterval: 1 },
    yAxis: { type: "value", name: "loss", scale: true },
    series: [
      {
        name: "train loss",
        type: "line",
        showSymbol: true,
        symbolSize: 5,
        data: run.trajectory.map((point) => [point.epoch, point.train_loss]),
      },
      {
        name: "validation loss",
        type: "line",
        showSymbol: true,
        symbolSize: 5,
        connectNulls: false,
        data: run.trajectory.filter((point) => point.validation_loss !== null).map((point) => [point.epoch, point.validation_loss]),
      },
    ],
  };
}

function studyDistributionOption(study: TrainingStudy): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 54, right: 18, top: 28, bottom: 46 },
    xAxis: { type: "category", name: "seed", data: study.seed_runs.map((run) => String(run.seed)) },
    yAxis: { type: "value", name: study.selection_metric, scale: true },
    series: [{ name: study.selection_metric, type: "bar", data: study.seed_runs.map((run) => run.validation_metrics[study.selection_metric] ?? null) }],
  };
}

function studyTrajectoryOption(study: TrainingStudy): EChartsOption {
  return {
    tooltip: { trigger: "axis" },
    legend: { type: "scroll", data: study.seed_runs.map((run) => `seed ${run.seed}`) },
    grid: { left: 54, right: 18, top: 44, bottom: 34 },
    xAxis: { type: "value", name: "epoch", minInterval: 1 },
    yAxis: { type: "value", name: "validation loss", scale: true },
    series: study.seed_runs.map((run) => ({
      name: `seed ${run.seed}`,
      type: "line",
      showSymbol: true,
      symbolSize: 5,
      connectNulls: false,
      data: run.trajectory
        .filter((point) => point.validation_loss !== null)
        .map((point) => [point.epoch, point.validation_loss]),
    })),
  };
}

function studyStatistics(study: TrainingStudy) {
  const values = study.seed_runs
    .map((run) => run.validation_metrics[study.selection_metric])
    .filter((value): value is number => typeof value === "number")
    .sort((left, right) => left - right);
  if (!values.length) return null;
  const mean = values.reduce((total, value) => total + value, 0) / values.length;
  const median = values.length % 2
    ? values[(values.length - 1) / 2]
    : (values[values.length / 2 - 1] + values[values.length / 2]) / 2;
  const variance = values.reduce((total, value) => total + (value - mean) ** 2, 0) / values.length;
  return { mean, median, std: Math.sqrt(variance), min: values[0], max: values[values.length - 1] };
}

function NumberField({ label, value, min, max, step = 1, disabled, onChange }: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return <label className="field-label">{label}<input type="number" value={value} min={min} max={max} step={step} disabled={disabled} onChange={(event) => {
    const next = Number(event.target.value);
    if (Number.isFinite(next)) onChange(next);
  }} /></label>;
}

function parseStudySeeds(value: string): { seeds: number[]; error: string | null } {
  const tokens = value.split(",").map((token) => token.trim());
  if (tokens.some((token) => !/^-?\d+$/.test(token) || !Number.isSafeInteger(Number(token)))) {
    return { seeds: [], error: "Use comma-separated whole-number seeds; invalid entries are not ignored." };
  }
  const seeds = tokens.map(Number);
  if (new Set(seeds).size !== seeds.length) return { seeds: [], error: "Each Study seed must be distinct." };
  if (seeds.length < 3) return { seeds: [], error: "Enter at least three distinct seeds to start a multi-seed Study." };
  if (seeds.length > 32) return { seeds: [], error: "A multi-seed Study accepts at most 32 seeds." };
  return { seeds, error: null };
}

type NumericConstraint = { minimum?: number; exclusiveMinimum?: number; maximum?: number; exclusiveMaximum?: number; nullable?: boolean };
const API_TRAINING_CONSTRAINTS: Record<string, NumericConstraint & { integer?: boolean }> = {
  max_epochs: { minimum: 1, maximum: 2000, integer: true },
  learning_rate: { exclusiveMinimum: 0, maximum: 1 },
  batch_size: { minimum: 1, maximum: 100000, integer: true },
  patience: { minimum: 1, maximum: 2000, nullable: true, integer: true },
  max_rules: { minimum: 1, maximum: 128, integer: true },
  n_estimators: { minimum: 1, maximum: 5000, nullable: true, integer: true },
  max_depth: { minimum: 1, maximum: 1000, nullable: true, integer: true },
};
const PARAMETER_LABELS: Record<string, string> = {
  max_epochs: "Epochs", learning_rate: "Learning rate", batch_size: "Batch size", patience: "Patience",
  max_rules: "Max rules / layer", n_estimators: "Trees / estimators", max_depth: "Maximum depth",
};

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  return JSON.stringify(value) ?? "undefined";
}

function numericConstraint(value: unknown): NumericConstraint {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const record = value as Record<string, unknown>;
  const result: NumericConstraint = {};
  for (const key of ["minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum"] as const) {
    if (typeof record[key] === "number" && Number.isFinite(record[key])) result[key] = record[key] as number;
  }
  if (typeof record.nullable === "boolean") result.nullable = record.nullable;
  return result;
}

function parameterBounds(name: string, declared: unknown): { min?: number; max?: number } {
  const constraints = [API_TRAINING_CONSTRAINTS[name], numericConstraint(declared)].filter((item): item is NumericConstraint => Boolean(item));
  const lower = constraints.flatMap((item) => [item.minimum, item.exclusiveMinimum]).filter((value): value is number => typeof value === "number");
  const upper = constraints.flatMap((item) => [item.maximum, item.exclusiveMaximum]).filter((value): value is number => typeof value === "number");
  return {
    min: lower.length ? Math.max(...lower) : undefined,
    max: upper.length ? Math.min(...upper) : undefined,
  };
}

function validateTrainingParameters(model: ModelCapabilityContract | null, values: Record<string, number | null>): string[] {
  if (!model) return [];
  const errors: string[] = [];
  for (const [name, declaredValue] of Object.entries(model.parameter_constraints)) {
    if (!(name in API_TRAINING_CONSTRAINTS) || !(name in values)) continue;
    const api = API_TRAINING_CONSTRAINTS[name];
    const declared = numericConstraint(declaredValue);
    const value = values[name];
    const label = PARAMETER_LABELS[name] ?? name;
    if (value === null) {
      if (!api.nullable || declared.nullable !== true) errors.push(`${label} cannot be empty for this model.`);
      continue;
    }
    if (!Number.isFinite(value) || (api.integer && !Number.isSafeInteger(value))) {
      errors.push(`${label} must be a finite${api.integer ? " whole-number" : ""} value.`);
      continue;
    }
    const constraints = [api, declared];
    const minimum = constraints.flatMap((item) => [item.minimum, item.exclusiveMinimum]).filter((bound): bound is number => typeof bound === "number");
    const maximum = constraints.flatMap((item) => [item.maximum, item.exclusiveMaximum]).filter((bound): bound is number => typeof bound === "number");
    if (constraints.some((item) => item.minimum !== undefined && value < item.minimum || item.exclusiveMinimum !== undefined && value <= item.exclusiveMinimum)) {
      const bound = Math.max(...minimum);
      errors.push(`${label} must be ${constraints.some((item) => item.exclusiveMinimum === bound) ? "greater than" : "at least"} ${bound}.`);
    }
    if (constraints.some((item) => item.maximum !== undefined && value > item.maximum || item.exclusiveMaximum !== undefined && value >= item.exclusiveMaximum)) {
      const bound = Math.min(...maximum);
      errors.push(`${label} must be ${constraints.some((item) => item.exclusiveMaximum === bound) ? "less than" : "at most"} ${bound}.`);
    }
  }
  return errors;
}

export function ExperimentWorkspace({ project, dataset, datasetHydrationStatus = "available", datasetHydrationError = null, onRetryDatasetHydration = () => undefined, run, study: restoredStudy, studyHydrationStatus = "available", studyHydrationError = null, onRetryStudyHydration = () => undefined, theme, onRun, onStudy, onStabilityAnalysisChange, onStabilityGatePolicyChange }: {
  project: ProjectSummary;
  dataset: DatasetState | null;
  datasetHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  datasetHydrationError?: string | null;
  onRetryDatasetHydration?: () => void;
  run: TrainingRun | null;
  study: TrainingStudy | null;
  studyHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  studyHydrationError?: string | null;
  onRetryStudyHydration?: () => void;
  theme: StudioTheme;
  onRun: (run: TrainingRun) => void;
  onStudy: (study: TrainingStudy) => void;
  onStabilityAnalysisChange?: (analysis: StudyStabilityAnalysis | null) => void;
  onStabilityGatePolicyChange?: (policy: StabilityGatePolicy | null) => void;
}) {
  const [seed, setSeed] = useState(42);
  const [modelKind, setModelKind] = useState("flat_neuro_fuzzy");
  const [maxEpochs, setMaxEpochs] = useState(20);
  const [learningRate, setLearningRate] = useState(0.01);
  const [batchSize, setBatchSize] = useState(32);
  const [patience, setPatience] = useState(8);
  const [maxRules, setMaxRules] = useState(8);
  const [nEstimators, setNEstimators] = useState(25);
  const [maxDepth, setMaxDepth] = useState<number | null>(null);
  const [seedList, setSeedList] = useState("42, 43, 44");
  const [studyMode, setStudyMode] = useState<"TRAINING_VARIABILITY" | "SPLIT_VARIABILITY" | "COMBINED_VARIABILITY">("TRAINING_VARIABILITY");
  const [splitSeed, setSplitSeed] = useState(42);
  const [splitFamily, setSplitFamily] = useState<SplitContract["family"]>("RANDOM");
  const [groupColumn, setGroupColumn] = useState("");
  const [rigorProfile, setRigorProfile] = useState<"EXPLORATORY" | "CONFIRMATORY" | "HIGH_ASSURANCE_LIKE">("CONFIRMATORY");
  const [splitContract, setSplitContract] = useState<SplitContract | null>(null);
  const [splitContractRecovery, setSplitContractRecovery] = useState<{ request: Parameters<typeof studioApi.createSplitContract>[1]; datasetFingerprint: string; datasetArtifactSha256: string; error: string; notFound: boolean } | null>(null);
  const [recoveringSplitContract, setRecoveringSplitContract] = useState(false);
  const [splitEvidenceStatus, setSplitEvidenceStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [splitEvidenceError, setSplitEvidenceError] = useState<string | null>(null);
  const [splitEvidenceReload, setSplitEvidenceReload] = useState(0);
  const [study, setStudy] = useState<TrainingStudy | null>(restoredStudy);
  const [studyJob, setStudyJob] = useState<StudyJob | null>(null);
  const [studyJobsStatus, setStudyJobsStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [studyJobsError, setStudyJobsError] = useState<string | null>(null);
  const [studyJobsReload, setStudyJobsReload] = useState(0);
  const [studyJobPollError, setStudyJobPollError] = useState<string | null>(null);
  const [pendingStudyRequest, setPendingStudyRequest] = useState<Parameters<typeof studioApi.startStudyJob>[1] | null>(null);
  const pendingStudyRequestRef = useRef<Parameters<typeof studioApi.startStudyJob>[1] | null>(null);
  const [running, setRunning] = useState(false);
  const [trainingRecovery, setTrainingRecovery] = useState<{ config: Parameters<typeof studioApi.runTraining>[1]; requestedAt: number; error: string; notFound: boolean } | null>(null);
  const [recoveringTraining, setRecoveringTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeSample, setTreeSample] = useState<Record<string, string>>({});
  const [treeEvidence, setTreeEvidence] = useState<TreePathEvidence | null>(null);
  const [treeEvidenceStatus, setTreeEvidenceStatus] = useState<"idle" | "loading" | "none" | "available" | "other_run" | "error">("idle");
  const [treeEvidenceError, setTreeEvidenceError] = useState<string | null>(null);
  const [treeEvidenceReload, setTreeEvidenceReload] = useState(0);
  const [treePathRecovery, setTreePathRecovery] = useState<{ runId: string; sample: Record<string, number>; error: string; notFound: boolean } | null>(null);
  const [treePathRecovering, setTreePathRecovering] = useState(false);
  const [transformPipeline, setTransformPipeline] = useState<TransformPipelineContract | null>(null);
  const [leakageAudit, setLeakageAudit] = useState<LeakageAuditReport | null>(null);
  const [runSplitContract, setRunSplitContract] = useState<SplitContract | null>(null);
  const [dataEvidenceState, setDataEvidenceState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [dataEvidenceError, setDataEvidenceError] = useState<string | null>(null);
  const [dataEvidenceReload, setDataEvidenceReload] = useState(0);
  const [catalog, setCatalog] = useState<ModelCapabilityContract[]>([]);
  const [catalogStatus, setCatalogStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogReload, setCatalogReload] = useState(0);
  const [executionBackends, setExecutionBackends] = useState<ExecutionBackendDescriptor[]>([]);
  const [executionBackendStatus, setExecutionBackendStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [executionBackendError, setExecutionBackendError] = useState<string | null>(null);
  const [executionBackendReload, setExecutionBackendReload] = useState(0);
  const [executionBackendKey, setExecutionBackendKey] = useState("local_executor");
  const [runCapabilities, setRunCapabilities] = useState<RunCapabilityNegotiation | null>(null);
  const [runCapabilitiesStatus, setRunCapabilitiesStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [runCapabilitiesError, setRunCapabilitiesError] = useState<string | null>(null);
  const [runCapabilitiesReload, setRunCapabilitiesReload] = useState(0);
  const option = useMemo(() => run ? trajectoryOption(run) : null, [run]);
  const statistics = useMemo(() => study ? studyStatistics(study) : null, [study]);
  const studySeedValidation = useMemo(() => parseStudySeeds(seedList), [seedList]);
  useEffect(() => {
    setStudy(restoredStudy);
  }, [restoredStudy?.study_id]);
  useEffect(() => {
    let active = true;
    setTreeEvidence(null);
    setTreeEvidenceError(null);
    if (!run || run.model_kind !== "decision_tree") { setTreeEvidenceStatus("idle"); return () => { active = false; }; }
    setTreeEvidenceStatus("loading");
    studioApi.getLatestTreePath(project.session_id).then((evidence) => {
      if (!active) return;
      if (evidence.run_id === run.run_id) {
        setTreeEvidence(evidence);
        setTreeEvidenceStatus("available");
      } else {
        setTreeEvidenceStatus("other_run");
      }
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setTreeEvidenceStatus("none");
        return;
      }
      setTreeEvidenceStatus("error");
      setTreeEvidenceError(reason instanceof Error ? reason.message : "Saved tree-path evidence could not be verified.");
    });
    return () => { active = false; };
  }, [project.session_id, run?.run_id, run?.model_kind, treeEvidenceReload]);
  useEffect(() => {
    let active = true;
    setTransformPipeline(null);
    setLeakageAudit(null);
    setRunSplitContract(null);
    setDataEvidenceError(null);
    if (!run) {
      setDataEvidenceState("idle");
      return () => { active = false; };
    }
    const pipelineId = run.transform_pipeline_id;
    const auditId = run.leakage_audit_id;
    const hasSplit = Boolean(run.split.split_contract_id);
    if (!pipelineId && !auditId && !hasSplit) {
      setDataEvidenceState("idle");
      return () => { active = false; };
    }
    if (!pipelineId || !auditId) {
      setDataEvidenceState("error");
      setDataEvidenceError("The saved run has incomplete data-governance references; the missing evidence is not treated as absent or valid.");
      return () => { active = false; };
    }
    setDataEvidenceState("loading");
    Promise.all([
      studioApi.getTransformPipeline(project.session_id, pipelineId),
      studioApi.getLeakageAudit(project.session_id, auditId),
      run.split.split_contract_id ? studioApi.getSplitContract(project.session_id, run.split.split_contract_id) : Promise.resolve(null),
    ]).then(([pipeline, audit, frozenSplit]) => {
      if (!active) return;
      if (pipeline.pipeline_id !== run.transform_pipeline_id || audit.audit_id !== run.leakage_audit_id || pipeline.dataset_fingerprint !== dataset?.contract.dataset_fingerprint || audit.dataset_fingerprint !== pipeline.dataset_fingerprint || pipeline.split_contract_id !== (frozenSplit?.split_id ?? null) || audit.split_contract_id !== (frozenSplit?.split_id ?? null) || audit.transform_pipeline_id !== pipeline.pipeline_id) throw new Error("Persisted data evidence identity does not match the selected run.");
      setTransformPipeline(pipeline);
      setLeakageAudit(audit);
      setRunSplitContract(frozenSplit);
      setDataEvidenceState("loaded");
    }).catch((reason: unknown) => {
      if (active) {
        setDataEvidenceState("error");
        setDataEvidenceError(reason instanceof Error ? reason.message : "Persisted data-governance evidence could not be reopened.");
      }
    });
    return () => { active = false; };
  }, [project.session_id, dataset?.contract.dataset_fingerprint, run?.run_id, run?.transform_pipeline_id, run?.leakage_audit_id, run?.split.split_contract_id, dataEvidenceReload]);
  useEffect(() => {
    let active = true;
    setSplitEvidenceStatus("loading");
    setSplitEvidenceError(null);
    studioApi.listSplitContracts(project.session_id).then((contracts) => {
      if (!active) return;
      const current = contracts.at(-1) ?? null;
      setSplitContract(current);
      if (current) { setSplitFamily(current.family); setGroupColumn(current.group_column ?? current.time_column ?? current.site_column ?? current.device_column ?? current.spatial_column ?? current.regime_column ?? ""); setSplitSeed(current.split_seed); }
      setSplitEvidenceStatus("loaded");
    }).catch((reason) => {
      if (!active) return;
      setSplitContract(null);
      setSplitEvidenceStatus("error");
      setSplitEvidenceError(reason instanceof Error ? reason.message : "Saved split provenance could not be verified.");
    });
    return () => { active = false; };
  }, [project.session_id, splitEvidenceReload]);
  useEffect(() => {
    let active = true;
    if (!run) { setRunCapabilities(null); setRunCapabilitiesStatus("idle"); setRunCapabilitiesError(null); return () => { active = false; }; }
    setRunCapabilities(null);
    setRunCapabilitiesStatus("loading");
    setRunCapabilitiesError(null);
    studioApi.getTrainingRunCapabilities(project.session_id, run.run_id).then((capabilities) => {
      if (!active) return;
      setRunCapabilities(capabilities);
      setRunCapabilitiesStatus("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setRunCapabilitiesStatus("error");
      setRunCapabilitiesError(reason instanceof Error ? reason.message : "Saved run capabilities could not be verified.");
    });
    return () => { active = false; };
  }, [project.session_id, run?.run_id, runCapabilitiesReload]);
  useEffect(() => {
    let active = true;
    setCatalogStatus("loading");
    setCatalogError(null);
    studioApi.getModels().then((models) => {
      if (!active) return;
      setCatalog(models);
      setCatalogStatus("loaded");
    }).catch((reason) => {
      if (!active) return;
      setCatalog([]);
      setCatalogError(reason instanceof Error ? reason.message : "Model capability catalog request failed.");
      setCatalogStatus("error");
    });
    return () => { active = false; };
  }, [catalogReload]);
  useEffect(() => {
    let active = true;
    setExecutionBackendStatus("loading");
    setExecutionBackendError(null);
    studioApi.getRuntimeBackends().then((backends) => {
      if (!active) return;
      setExecutionBackends(backends);
      if (!backends.some((backend) => backend.identity.key === executionBackendKey)) setExecutionBackendKey(backends[0]?.identity.key ?? "local_executor");
      setExecutionBackendStatus("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setExecutionBackends([]);
      setExecutionBackendError(reason instanceof Error ? reason.message : "Execution backend catalog could not be verified.");
      setExecutionBackendStatus("error");
    });
    return () => { active = false; };
  }, [executionBackendReload]);
  const datasetTask = dataset?.contract.task;
  const compatibleModels = useMemo(() => catalog.filter((entry) => entry.available && entry.capabilities.fit && !!datasetTask && entry.supported_tasks.includes(datasetTask)), [catalog, datasetTask]);
  const selectedModel = compatibleModels.find((entry) => entry.training_model_kinds.includes(modelKind)) ?? null;
  const selectedAdapterKey = selectedModel?.provider === "ruflex.builtin" ? null : selectedModel?.key ?? null;
  const supportsParameter = (name: string) => Boolean(selectedModel?.parameter_constraints[name]);
  const trainingParameterValues: Record<string, number | null> = { max_epochs: maxEpochs, learning_rate: learningRate, batch_size: batchSize, patience, max_rules: maxRules, n_estimators: nEstimators, max_depth: maxDepth };
  const parameterErrors = useMemo(() => validateTrainingParameters(selectedModel, trainingParameterValues), [selectedModel, maxEpochs, learningRate, batchSize, patience, maxRules, nEstimators, maxDepth]);
  const canExactTreePath = runCapabilities?.decisions.some((decision) => decision.capability === "exact_tree_path" && decision.status === "AVAILABLE") ?? false;
  useEffect(() => {
    const defaults = selectedModel?.defaults;
    if (!defaults) return;
    if (typeof defaults.max_epochs === "number") setMaxEpochs(defaults.max_epochs);
    if (typeof defaults.learning_rate === "number") setLearningRate(defaults.learning_rate);
    if (typeof defaults.batch_size === "number") setBatchSize(defaults.batch_size);
    if (typeof defaults.patience === "number") setPatience(defaults.patience);
    if (typeof defaults.max_rules === "number") setMaxRules(defaults.max_rules);
    if (typeof defaults.n_estimators === "number") setNEstimators(defaults.n_estimators);
    if ("max_depth" in defaults) setMaxDepth(typeof defaults.max_depth === "number" ? defaults.max_depth : null);
  }, [selectedModel?.key]);
  useEffect(() => {
    if (compatibleModels.length && !compatibleModels.some((entry) => entry.training_model_kinds.includes(modelKind))) setModelKind(compatibleModels[0].training_model_kinds[0]);
  }, [compatibleModels, modelKind]);
  const trainingModelKind = modelKind;
  useEffect(() => {
    let active = true;
    setStudyJobsStatus("loading");
    setStudyJobsError(null);
    studioApi.listStudyJobs(project.session_id).then((jobs) => {
      if (!active) return;
      const latest = [...jobs].reverse();
      const resumable = latest.find((job) => ["QUEUED", "RUNNING"].includes(job.status));
      const restoredStudyJob = restoredStudy
        ? latest.find((job) => job.study_id === restoredStudy.study_id)
        : undefined;
      setStudyJob(resumable ?? restoredStudyJob ?? latest[0] ?? null);
      setStudyJobsStatus("loaded");
    }).catch((reason) => {
      if (!active) return;
      setStudyJobsError(reason instanceof Error ? reason.message : "Saved Study jobs could not be restored.");
      setStudyJobsStatus("error");
    });
    return () => { active = false; };
  }, [project.session_id, restoredStudy?.study_id, studyJobsReload]);

  async function observeStudy(initial: StudyJob) {
    let job = initial;
    setStudyJobPollError(null);
    setStudyJob(job);
    while (["QUEUED", "RUNNING"].includes(job.status)) {
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      try {
        job = await studioApi.getStudyJob(project.session_id, job.job_id);
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : "Could not refresh the persisted Study job status.";
        setStudyJobPollError(message);
        return;
      }
      setStudyJob(job);
    }
    if (job.status !== "SUCCEEDED") throw new Error(job.error ?? `Study ${job.status.toLowerCase()}`);
    const result = await studioApi.getLatestTrainingStudy(project.session_id);
    setStudy(result); onStudy(result);
    setStudyJobsStatus("loaded");
    const selected = result.seed_runs.find((item) => item.run_id === result.selected_run_id);
    if (selected) onRun(selected);
  }

  async function train() {
    if (splitContractRecovery || trainingRecovery) return;
    setRunning(true);
    setError(null);
    const config: Parameters<typeof studioApi.runTraining>[1] = {
      model_kind: trainingModelKind, adapter_key: selectedAdapterKey,
      seed, split_seed: splitContract?.split_seed ?? null, training_seed: seed, split_contract_id: splitContract?.split_id ?? null,
      rigor_profile: rigorProfile,
      max_epochs: maxEpochs,
      learning_rate: learningRate,
      batch_size: batchSize,
      patience,
      validation_fraction: 0.2,
      test_fraction: 0.2,
      max_rules: maxRules,
      n_estimators: nEstimators,
      max_depth: maxDepth,
    };
    const requestedAt = Date.now();
    try {
      onRun(await studioApi.runTraining(project.session_id, config)); setTrainingRecovery(null);
    } catch (reason) {
      setTrainingRecovery({ config, requestedAt, error: reason instanceof Error ? reason.message : "Training result response was uncertain.", notFound: false });
      setError(reason instanceof Error ? reason.message : "Training failed");
    } finally {
      setRunning(false);
    }
  }
  async function recoverTrainingRun() {
    const pending = trainingRecovery;
    if (!pending) return;
    setRecoveringTraining(true); setError(null);
    try {
      const matches = (await studioApi.getTrainingRuns(project.session_id)).filter((candidate) => trainingRunMatchesRecovery(candidate, pending, dataset));
      if (matches.length === 1) {
        onRun(matches[0]); setTrainingRecovery(null); return;
      }
      if (matches.length > 1) {
        setTrainingRecovery({ ...pending, notFound: false, error: "Multiple runs match this request window and configuration. No run was selected; reopen run history and resolve the exact persisted identity." });
        return;
      }
      setTrainingRecovery({ ...pending, notFound: true, error: "No matching persisted TrainingRun is visible yet. Retry lookup later, or explicitly start a new fit with the frozen original settings." });
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not verify persisted TrainingRun history.";
      setTrainingRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { setRecoveringTraining(false); }
  }
  async function explicitlyRepeatTraining() {
    const pending = trainingRecovery;
    if (!pending?.notFound || project.read_only) return;
    setRecoveringTraining(true); setRunning(true); setError(null);
    try { onRun(await studioApi.runTraining(project.session_id, pending.config)); setTrainingRecovery(null); }
    catch (reason) {
      const message = reason instanceof Error ? reason.message : "The explicitly repeated training request could not be confirmed.";
      setTrainingRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { setRecoveringTraining(false); setRunning(false); }
  }
  async function freezeSplitContract() {
    if (splitContractRecovery) return;
    if (!dataset) { setError("Confirm a DatasetContract before freezing split provenance."); return; }
    setRunning(true); setError(null);
    try {
      if (splitFamily !== "RANDOM" && !groupColumn) throw new Error("Choose the declared identity column before freezing this split.");
      const identity = splitFamily === "GROUP" ? { group_column: groupColumn } : splitFamily === "TEMPORAL" ? { time_column: groupColumn } : splitFamily === "SITE_HOLDOUT" ? { site_column: groupColumn } : splitFamily === "DEVICE_HOLDOUT" ? { device_column: groupColumn } : splitFamily === "SPATIAL" ? { spatial_column: groupColumn } : splitFamily === "REGIME" ? { regime_column: groupColumn } : {};
      const request = { family: splitFamily, split_seed: splitSeed, validation_fraction: .2, test_fraction: .2, ...identity } as Parameters<typeof studioApi.createSplitContract>[1];
      try {
        const created = await studioApi.createSplitContract(project.session_id, request);
        setSplitContract(created); setSplitContractRecovery(null);
      } catch (reason) {
        setSplitContractRecovery({ request, datasetFingerprint: dataset.contract.dataset_fingerprint, datasetArtifactSha256: dataset.contract.source_artifact_sha256, error: reason instanceof Error ? reason.message : "SplitContract response was uncertain.", notFound: false });
        throw reason;
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not freeze split contract"); }
    finally { setRunning(false); }
  }
  function splitContractMatchesRecovery(candidate: SplitContract, pending: NonNullable<typeof splitContractRecovery>): boolean {
    const request = pending.request;
    return candidate.dataset_fingerprint === pending.datasetFingerprint
      && candidate.dataset_artifact_sha256 === pending.datasetArtifactSha256
      && candidate.family === request.family
      && candidate.split_seed === request.split_seed
      && candidate.validation_fraction === request.validation_fraction
      && candidate.test_fraction === request.test_fraction
      && candidate.group_column === (request.group_column ?? null)
      && candidate.time_column === (request.time_column ?? null)
      && candidate.site_column === (request.site_column ?? null)
      && candidate.device_column === (request.device_column ?? null)
      && candidate.spatial_column === (request.spatial_column ?? null)
      && candidate.regime_column === (request.regime_column ?? null);
  }
  async function recoverSplitContract() {
    const pending = splitContractRecovery;
    if (!pending) return;
    setRecoveringSplitContract(true); setError(null);
    try {
      const matches = (await studioApi.listSplitContracts(project.session_id)).filter((candidate) => splitContractMatchesRecovery(candidate, pending));
      const latest = matches.at(-1);
      if (!latest) {
        setSplitContractRecovery({ ...pending, notFound: true, error: "No matching saved SplitContract is visible yet. Retry lookup later, or explicitly repeat these exact split settings." });
        return;
      }
      setSplitContract(latest); setSplitContractRecovery(null);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Could not recover the exact SplitContract.";
      setSplitContractRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { setRecoveringSplitContract(false); }
  }
  async function explicitlyRepeatSplitContract() {
    const pending = splitContractRecovery;
    if (!pending?.notFound || project.read_only || dataset?.contract.dataset_fingerprint !== pending.datasetFingerprint || dataset.contract.source_artifact_sha256 !== pending.datasetArtifactSha256) return;
    setRecoveringSplitContract(true); setRunning(true); setError(null);
    try {
      setSplitContract(await studioApi.createSplitContract(project.session_id, pending.request)); setSplitContractRecovery(null);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The explicitly repeated SplitContract could not be confirmed.";
      setSplitContractRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { setRecoveringSplitContract(false); setRunning(false); }
  }
  async function trainStudy() {
    const pendingRequest = pendingStudyRequestRef.current;
    if (pendingRequest) {
      setRunning(true);
      setError(null);
      try {
        const job = await studioApi.startStudyJob(project.session_id, pendingRequest);
        pendingStudyRequestRef.current = null;
        setPendingStudyRequest(null);
        await observeStudy(job);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "The original Study request could not be recovered.");
      } finally {
        setRunning(false);
      }
      return;
    }
    if (studyJob && ["QUEUED", "RUNNING"].includes(studyJob.status)) {
      setError("A persisted StudyJob is still active. Resume or inspect that exact job before starting another set of fits.");
      return;
    }
    if (splitContractRecovery) return;
    if (studySeedValidation.error) {
      setError(studySeedValidation.error);
      return;
    }
    if (studyHydrationStatus !== "none" && studyHydrationStatus !== "available") {
      setError("Resolve saved TrainingStudy status before starting another multi-seed Study.");
      return;
    }
    if (studyJobsStatus !== "loaded") {
      setError("Resolve saved Study job status before starting another multi-seed Study.");
      return;
    }
    const seeds = studySeedValidation.seeds;
    setRunning(true);
    setError(null);
    try {
      const selectionMetric = dataset?.contract.task === "regression" ? "rmse" : "f1";
      if (splitContract && studyMode !== "TRAINING_VARIABILITY") throw new Error("A frozen SplitContract can be used only with fixed-split training variability studies.");
      const request: Parameters<typeof studioApi.startStudyJob>[1] = { client_request_id: crypto.randomUUID(), name: `Study ${new Date().toLocaleString()}`, model_kind: trainingModelKind, adapter_key: selectedAdapterKey, seeds, randomness_protocol: studyMode, split_seed: splitContract?.split_seed ?? splitSeed, training_seed: splitSeed, split_contract_id: splitContract?.split_id ?? null, execution_backend_key: executionBackendKey, selection_metric: selectionMetric, max_epochs: maxEpochs, learning_rate: learningRate, batch_size: batchSize, patience, validation_fraction: .2, test_fraction: .2, max_rules: maxRules, n_estimators: nEstimators, max_depth: maxDepth };
      pendingStudyRequestRef.current = request;
      setPendingStudyRequest(request);
      let job = await studioApi.startStudyJob(project.session_id, request);
      pendingStudyRequestRef.current = null;
      setPendingStudyRequest(null);
      await observeStudy(job);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Multi-seed study failed");
    } finally {
      setRunning(false);
    }
  }
  async function traceTree() {
    if (!run || treePathRecovery) return;
    const sample = Object.fromEntries(run.feature_columns.map((column) => [column, Number(treeSample[column])])) as Record<string, number>;
    if (Object.values(sample).some((value) => !Number.isFinite(value))) {
      setError("Enter a finite value for every tree feature.");
      return;
    }
    setRunning(true); setError(null);
    try {
      let evidence: TreePathEvidence;
      try { evidence = await studioApi.createTreePath(project.session_id, run.run_id, sample); }
      catch (reason) {
        setTreePathRecovery({ runId: run.run_id, sample, error: reason instanceof Error ? reason.message : "Tree-path trace response was uncertain.", notFound: false });
        throw reason;
      }
      setTreeEvidence(evidence);
      setTreeEvidenceStatus("available");
      setTreeEvidenceError(null);
      setTreePathRecovery(null);
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Tree path trace failed"); }
    finally { setRunning(false); }
  }
  async function recoverTreePath() {
    const pending = treePathRecovery;
    if (!pending) return;
    setTreePathRecovering(true); setError(null);
    try {
      const latest = await studioApi.getLatestTreePath(project.session_id);
      if (latest.run_id !== pending.runId || canonicalJson(latest.input_sample) !== canonicalJson(pending.sample)) {
        setTreePathRecovery({ ...pending, notFound: true, error: "The latest tree trace has different run/sample identity; no replacement was created." });
        return;
      }
      setTreeEvidence(latest); setTreeEvidenceStatus("available"); setTreeEvidenceError(null); setTreePathRecovery(null);
    } catch (reason) {
      if (reason instanceof ProductApiError && reason.status === 404) {
        setTreePathRecovery({ ...pending, notFound: true, error: "No matching tree trace is visible yet. Retry lookup later, or explicitly repeat this exact trace if the original did not finish." });
      } else {
        const message = reason instanceof Error ? reason.message : "Could not recover the exact tree trace.";
        setTreePathRecovery({ ...pending, notFound: false, error: message }); setError(message);
      }
    } finally { setTreePathRecovering(false); }
  }
  async function explicitlyRepeatTreePath() {
    const pending = treePathRecovery;
    if (!pending?.notFound || run?.run_id !== pending.runId) return;
    setRunning(true); setError(null);
    try {
      const evidence = await studioApi.createTreePath(project.session_id, pending.runId, pending.sample);
      setTreeEvidence(evidence); setTreeEvidenceStatus("available"); setTreeEvidenceError(null); setTreePathRecovery(null);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The explicitly repeated tree trace could not be confirmed.";
      setTreePathRecovery({ ...pending, notFound: false, error: message }); setError(message);
    } finally { setRunning(false); }
  }
  async function cancelStudy() {
    if (!studyJob || !["QUEUED", "RUNNING"].includes(studyJob.status)) return;
    try { setStudyJob(await studioApi.cancelStudyJob(project.session_id, studyJob.job_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not cancel Study"); }
  }
  async function resumeStudy() {
    if (!studyJob || !["QUEUED", "RUNNING"].includes(studyJob.status)) return;
    setRunning(true); setError(null);
    try { await observeStudy(await studioApi.resumeStudyJob(project.session_id, studyJob.job_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not resume Study"); }
    finally { setRunning(false); }
  }

  async function retryStudyStatus() {
    if (!studyJob) return;
    setRunning(true);
    setError(null);
    setStudyJobPollError(null);
    try { await observeStudy(await studioApi.getStudyJob(project.session_id, studyJob.job_id)); }
    catch (reason) { setStudyJobPollError(reason instanceof Error ? reason.message : "Could not refresh the persisted Study job status."); }
    finally { setRunning(false); }
  }

  if (datasetHydrationStatus !== "available" || !dataset) return <section className="feature-workspace">
    {datasetHydrationStatus === "loading" || datasetHydrationStatus === "idle" ? <div role="status">{datasetHydrationStatus === "loading" ? "Loading the persisted DatasetContract before enabling training…" : "Dataset state has not been checked."}</div> : datasetHydrationStatus === "error" ? <div className="error" role="alert"><strong>Could not restore the persisted DatasetContract.</strong><p>{datasetHydrationError ?? "No empty-dataset state is inferred from this failure. Training is paused."}</p><Button view="outlined" onClick={onRetryDatasetHydration}>Retry dataset check</Button>{run && <p>Saved run {run.run_id.slice(0, 12)} remains loaded; its validation metrics are retained while dataset-dependent actions are paused.</p>}</div> : <EmptyState title="No confirmed dataset">Confirm a DatasetContract in Data before training a model.</EmptyState>}
  </section>;

  return <section className="feature-workspace training-workspace">
    <div className="feature-toolbar">
      <div><span className="eyebrow">REAL TRAINING ENGINE</span><h2>Train a model revision</h2><p>Canonical train-only preprocessing · held-out test remains locked.</p></div>
      <StatusBadge tone={running ? "warning" : run ? "success" : "info"}>{running ? "Training" : run ? "Completed run" : "Ready"}</StatusBadge>
    </div>

    <div className="training-grid">
      <section className="training-config-panel">
        <h3>Protocol</h3>
        {studyHydrationStatus === "loading" && <p role="status">Checking for a saved TrainingStudy…</p>}
        {studyHydrationStatus === "idle" && <p role="status">Saved TrainingStudy status has not been checked.</p>}
        {studyHydrationStatus === "none" && <p className="info-message" role="status">No saved TrainingStudy exists for this project yet; completed individual runs remain available.</p>}
        {studyHydrationStatus === "error" && <div className="error" role="alert"><strong>Could not restore saved TrainingStudy.</strong> {studyHydrationError ?? "No empty Study state is inferred from this failure."} <Button view="outlined" size="s" onClick={onRetryStudyHydration}>Retry Study check</Button></div>}
        {studyJobsStatus === "loading" && <p role="status">Checking saved Study jobs…</p>}
        {studyJobsStatus === "error" && <div className="error" role="alert"><strong>Could not restore saved Study jobs.</strong> {studyJobsError ?? "No empty job state is inferred from this failure."} <Button view="outlined" size="s" onClick={() => setStudyJobsReload((current) => current + 1)}>Retry Study jobs</Button></div>}
        <dl className="compact-definition">
          <dt>Target</dt><dd>{dataset.contract.target}</dd>
          <dt>Task</dt><dd>{dataset.contract.task}</dd>
          <dt>Features</dt><dd>{dataset.contract.feature_columns.join(", ")}</dd>
          <dt>Split</dt><dd>60% train · 20% validation · 20% locked test</dd>
          <dt>Frozen split</dt><dd>{splitContract ? `${splitContract.family} · ${splitContract.split_id.slice(0, 8)}` : "No explicit contract — legacy random holdout"}</dd>
          <dt>Preprocessing</dt><dd>train-only median/mode fill + ordinal encoding + standardization</dd>
        </dl>
        <div className="training-config-grid">
          <label className="field-label">Model<select aria-label="Training model" value={modelKind} disabled={running || project.read_only || !compatibleModels.length} onChange={(event) => setModelKind(event.target.value)}>{compatibleModels.map((entry) => <option key={entry.key} value={entry.key === "linear" ? (datasetTask === "regression" ? "linear_regression" : "logistic_regression") : entry.training_model_kinds[0]}>{entry.display_name}</option>)}</select></label>
          <NumberField label="Seed" value={seed} step={1} disabled={running || project.read_only} onChange={setSeed} />
          <NumberField label="Study split seed" value={splitSeed} step={1} disabled={running || project.read_only} onChange={setSplitSeed} />
          <label className="field-label">Split family<select aria-label="Split family" value={splitFamily} disabled={running || project.read_only} onChange={(event) => setSplitFamily(event.target.value as SplitContract["family"])}><option value="RANDOM">Random holdout</option><option value="GROUP">Group holdout</option><option value="TEMPORAL">Temporal holdout</option><option value="SITE_HOLDOUT">Site holdout</option><option value="DEVICE_HOLDOUT">Device holdout</option><option value="SPATIAL">Spatial-block holdout</option><option value="REGIME">Regime holdout</option></select></label>
          {splitFamily !== "RANDOM" && <label className="field-label">{splitFamily === "TEMPORAL" ? "Time" : "Declared identity"}<select aria-label="Split identity column" value={groupColumn} disabled={running || project.read_only} onChange={(event) => setGroupColumn(event.target.value)}><option value="">Choose column</option>{dataset.profile.columns.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}</select></label>}
          <label className="field-label">Rigor profile<select aria-label="Rigor profile" value={rigorProfile} disabled={running || project.read_only} onChange={(event) => setRigorProfile(event.target.value as typeof rigorProfile)}><option value="EXPLORATORY">Exploratory</option><option value="CONFIRMATORY">Confirmatory</option><option value="HIGH_ASSURANCE_LIKE">High-assurance-like</option></select></label>
          {supportsParameter("max_epochs") && <NumberField label="Epochs" value={maxEpochs} {...parameterBounds("max_epochs", selectedModel?.parameter_constraints.max_epochs)} step={1} disabled={running || project.read_only} onChange={setMaxEpochs} />}
          {supportsParameter("learning_rate") && <NumberField label="Learning rate" value={learningRate} {...parameterBounds("learning_rate", selectedModel?.parameter_constraints.learning_rate)} step={0.001} disabled={running || project.read_only} onChange={setLearningRate} />}
          {supportsParameter("batch_size") && <NumberField label="Batch size" value={batchSize} {...parameterBounds("batch_size", selectedModel?.parameter_constraints.batch_size)} step={1} disabled={running || project.read_only} onChange={setBatchSize} />}
          {supportsParameter("patience") && <NumberField label="Patience" value={patience} {...parameterBounds("patience", selectedModel?.parameter_constraints.patience)} step={1} disabled={running || project.read_only} onChange={setPatience} />}
          {supportsParameter("max_rules") && <NumberField label="Max rules / layer" value={maxRules} {...parameterBounds("max_rules", selectedModel?.parameter_constraints.max_rules)} step={1} disabled={running || project.read_only} onChange={setMaxRules} />}
          {supportsParameter("n_estimators") && <NumberField label="Trees / estimators" value={nEstimators} {...parameterBounds("n_estimators", selectedModel?.parameter_constraints.n_estimators)} step={1} disabled={running || project.read_only} onChange={setNEstimators} />}
          {supportsParameter("max_depth") && <label className="field-label">Maximum depth<input aria-label="Maximum depth" type="number" min={parameterBounds("max_depth", selectedModel?.parameter_constraints.max_depth).min} max={parameterBounds("max_depth", selectedModel?.parameter_constraints.max_depth).max} value={maxDepth ?? ""} placeholder="unlimited" disabled={running || project.read_only} onChange={(event) => setMaxDepth(event.target.value === "" ? null : Number(event.target.value))} /></label>}
          <label className="field-label">Study seeds<input aria-label="Study seeds" aria-invalid={Boolean(studySeedValidation.error)} aria-describedby="study-seeds-help" value={seedList} disabled={running || project.read_only} onChange={(event) => setSeedList(event.target.value)} /></label>
          <label className="field-label">Study randomness protocol<select aria-label="Study randomness protocol" value={studyMode} disabled={running || project.read_only} onChange={(event) => setStudyMode(event.target.value as typeof studyMode)}><option value="TRAINING_VARIABILITY">Training variability (fixed split)</option><option value="SPLIT_VARIABILITY">Split variability (fixed training seed)</option><option value="COMBINED_VARIABILITY">Combined variability</option></select></label>
          <label className="field-label">Study execution backend<select aria-label="Study execution backend" value={executionBackendKey} disabled={running || project.read_only || executionBackendStatus !== "loaded" || !executionBackends.length} onChange={(event) => setExecutionBackendKey(event.target.value)}>{executionBackends.map((backend) => <option key={backend.identity.key} value={backend.identity.key}>{backend.identity.key} · {backend.identity.provider}</option>)}</select></label>
        </div>
        {executionBackendStatus === "loading" && <p role="status">Checking available Study execution backends…</p>}
        {executionBackendStatus === "error" && <div className="error" role="alert" data-testid="execution-backend-catalog-error"><strong>Could not verify Study execution backends.</strong> {executionBackendError} <Button view="outlined" size="s" onClick={() => setExecutionBackendReload((current) => current + 1)}>Retry backend check</Button></div>}
        {executionBackendStatus === "loaded" && executionBackends.length === 0 && <p role="status">No Study execution backend is currently available.</p>}
        {catalogStatus === "loading" && <p role="status">Checking available model adapters for this task…</p>}
        {catalogStatus === "error" && <div className="error" role="alert"><strong>Could not check available models.</strong> {catalogError} <Button view="outlined" size="s" onClick={() => setCatalogReload((current) => current + 1)} data-ruflex-action="training.catalog.retry">Retry model check</Button></div>}
        {catalogStatus === "loaded" && compatibleModels.length === 0 && <div className="info-message" role="status"><strong>No compatible model is available.</strong> The catalog loaded, but no available adapter declares fit support for {datasetTask}. Training remains disabled; install/register a compatible adapter or choose a dataset for a supported task.</div>}
        {splitContractRecovery && <div className="error" role="alert" data-testid="split-contract-recovery"><strong>SplitContract save is uncertain; training is paused.</strong><p>{splitContractRecovery.error}</p><Button view="outlined" disabled={recoveringSplitContract} onClick={recoverSplitContract}>Retry exact SplitContract lookup</Button>{splitContractRecovery.notFound && <Button view="outlined" disabled={recoveringSplitContract || running || project.read_only} onClick={explicitlyRepeatSplitContract}>Explicitly repeat these exact split settings</Button>}</div>}
        <Button view="outlined" disabled={running || !!splitContractRecovery || project.read_only || splitEvidenceStatus !== "loaded"} onClick={freezeSplitContract} data-ruflex-action="split.freeze">Freeze {splitFamily} SplitContract</Button>
        <section className="info-message" aria-label="Training choices">
          <strong>Choose how to start</strong>
          <p><strong>Run real training</strong> creates one fitted TrainingRun for the current settings.</p>
          <p><strong>Run multi-seed study</strong> executes the distinct seeds listed above under the selected randomness protocol and preserves the per-seed results as a TrainingStudy. It requires at least three seeds.</p>
          <p>Both paths use the declared training/validation workflow; opening this screen or changing settings does not start computation or unlock the test split.</p>
        </section>
        {trainingRecovery && <div className="error" role="alert" data-testid="training-run-recovery"><strong>Training response is uncertain; no second fit was started.</strong><p>{trainingRecovery.error}</p><Button view="outlined" disabled={recoveringTraining} onClick={recoverTrainingRun}>Retry exact TrainingRun lookup</Button>{trainingRecovery.notFound && <Button view="outlined" disabled={recoveringTraining || running || project.read_only} onClick={explicitlyRepeatTraining}>Explicitly start a new fit with these settings</Button>}</div>}
        <Button view="action" disabled={running || !!trainingRecovery || !!splitContractRecovery || project.read_only || splitEvidenceStatus !== "loaded" || catalogStatus !== "loaded" || !selectedModel || parameterErrors.length > 0} onClick={train} data-ruflex-action="training.run">{running ? "Training…" : "Run real training"}</Button>
        <p id="study-seeds-help" className={studySeedValidation.error ? "error" : "property-description"} role={studySeedValidation.error ? "alert" : undefined}>{studySeedValidation.error ?? "Enter 3–32 distinct whole-number seeds, separated by commas."}</p>
        {parameterErrors.length > 0 && <div className="error" role="alert">Review model settings before training: {parameterErrors.join(" ")}</div>}
        <Button view="outlined" disabled={running || project.read_only || (!pendingStudyRequest && (!!(studyJob && ["QUEUED", "RUNNING"].includes(studyJob.status)) || !!trainingRecovery || !!splitContractRecovery || splitEvidenceStatus !== "loaded" || catalogStatus !== "loaded" || !selectedModel || Boolean(studySeedValidation.error) || parameterErrors.length > 0 || (studyHydrationStatus !== "none" && studyHydrationStatus !== "available") || studyJobsStatus !== "loaded" || executionBackendStatus !== "loaded" || !executionBackends.some((backend) => backend.identity.key === executionBackendKey)))} onClick={trainStudy} data-ruflex-action="study.start">{running ? "Training…" : pendingStudyRequest ? "Retry same Study request" : "Run multi-seed study"}</Button>
        {pendingStudyRequest && !running && <p role="status">Study submission status is uncertain. Retry uses the same request ID and frozen configuration; it will recover the existing job or safely report a mismatch.</p>}
        {studyJob && <div className="info-message"><strong>Study job {studyJob.status}</strong> · {studyJob.execution_backend_key ?? studyJob.execution_backend} · {studyJob.seed_states.map((state) => `seed ${state.seed}: ${state.status}`).join(" · ")} {(["QUEUED", "RUNNING"].includes(studyJob.status) && !studyJob.cancel_requested) && <><Button view="flat" size="s" disabled={running} onClick={resumeStudy} data-ruflex-action="study.resume">Resume persisted study</Button><Button view="flat" size="s" disabled={running} onClick={cancelStudy} data-ruflex-action="study.cancel">Cancel study</Button></>} {studyJob.cancel_requested && ["QUEUED", "RUNNING"].includes(studyJob.status) && <small role="status">Cancellation requested. The active seed fit may finish; remaining seeds will not start, and this job cannot be resumed.</small>} {studyJob.recovery_note && <small>{studyJob.recovery_note}</small>}{studyJobPollError && <div className="error" role="alert"><strong>Study status could not be refreshed.</strong> {studyJobPollError} <Button view="outlined" size="s" disabled={running} onClick={retryStudyStatus}>Retry Study status</Button></div>}</div>}
        {studyJob?.status === "CANCELLED" && <p className="property-description">This StudyJob is terminal and cannot be resumed. Seed fits completed before cancellation remain persisted; starting another Study creates new fits.</p>}
        {studyJob?.status === "FAILED" && <p className="property-description">This StudyJob is terminal and did not produce a selected TrainingStudy. Review the per-seed errors before starting another set of fits.</p>}
        {studyJob?.error && <p className="error" role="alert">StudyJob error: {studyJob.error}</p>}
        {studyJob?.seed_states.filter((state) => state.error).map((state) => <p className="error" role="alert" key={`${studyJob.job_id}-${state.seed}`}>Seed {state.seed}: {state.error}</p>)}
        <div className="info-message">A frozen SplitContract assigns exact source rows before fitting. GROUP keeps each declared identity in one role. It makes split membership auditable; it does not by itself establish generalization validity.</div>
        {splitEvidenceStatus === "loading" && <div role="status">Checking saved split provenance before enabling training…</div>}
        {splitEvidenceStatus === "error" && <div className="error" role="alert"><strong>Saved split provenance is unavailable.</strong> Training is blocked rather than falling back to an unverified split. {splitEvidenceError} <Button view="outlined" size="s" onClick={() => setSplitEvidenceReload((current) => current + 1)}>Retry saved split check</Button></div>}
        {project.read_only && <div className="info-message">Read-only projects cannot start training runs.</div>}
      </section>

      <section className="training-result-panel">
        {!run || !option ? <EmptyState title="No training run yet">Start a run to produce an actual model artifact and training trajectory.</EmptyState> : <>
          {run.model_kind === "decision_tree" && runCapabilitiesStatus === "loading" && <p role="status">Checking exact tree-path support for this persisted run…</p>}
          {run.model_kind === "decision_tree" && runCapabilitiesStatus === "error" && <div className="error" role="alert"><strong>Could not verify saved run capabilities.</strong> {runCapabilitiesError} Exact tree-path actions remain unavailable until this run is checked. <Button view="outlined" size="s" onClick={() => setRunCapabilitiesReload((current) => current + 1)}>Retry run capability check</Button></div>}
          <div className="run-summary-strip">
            <div><span>Epoch 0</span><strong>{run.trajectory[0]?.validation_loss?.toFixed(5) ?? "—"}</strong></div>
            <div><span>Best epoch</span><strong>{run.training_summary.best_epoch}</strong></div>
            <div><span>Epochs ran</span><strong>{run.training_summary.epochs_ran}</strong></div>
            <div><span>Best {run.training_summary.monitor_name}</span><strong>{run.training_summary.best_monitor_value.toFixed(5)}</strong></div>
          </div>
          <ChartSurface title="Training trajectory · epoch 0 included" option={option} theme={theme} />
          <div className="run-provenance">
            <StatusBadge tone="success">model artifact persisted</StatusBadge>
            <code>{run.model_artifact_sha256.slice(0, 24)}…</code>
            {run.adapter_key && run.adapter_version && <><StatusBadge tone="info">runtime adapter</StatusBadge><code data-testid="run-adapter-identity">{run.adapter_key}@{run.adapter_version}</code></>}
            {run.preprocessing_artifact_sha256 && <><StatusBadge tone="success">train-only preprocessing persisted</StatusBadge><code>{run.preprocessing_artifact_sha256.slice(0, 24)}…</code></>}
            {run.transform_pipeline_id && <><StatusBadge tone="success">transform pipeline frozen</StatusBadge><code>{run.transform_pipeline_id.slice(0, 12)}…</code></>}
            {run.leakage_audit_id && <><StatusBadge tone="success">leakage audit persisted</StatusBadge><code>{run.leakage_audit_id.slice(0, 12)}…</code></>}
            <span>seed {run.seed}</span>
            <span>{run.split.train_count}/{run.split.validation_count}/{run.split.test_count} rows</span>
          </div>
          <details className="data-governance-evidence" data-testid="data-governance-evidence">
            <summary>Data governance evidence</summary>
            {dataEvidenceState === "loading" && <p role="status">Loading persisted split, preprocessing and leakage-audit evidence…</p>}
            {dataEvidenceState === "error" && <div className="error" role="alert"><strong>Could not verify this run’s data-governance evidence.</strong> {dataEvidenceError ?? "The saved run references are not treated as verified."} <Button view="outlined" size="s" onClick={() => setDataEvidenceReload((current) => current + 1)}>Retry data evidence</Button></div>}
            {dataEvidenceState === "idle" && <p>No persisted transform or leakage-audit evidence is linked to this run.</p>}
            {dataEvidenceState === "loaded" && transformPipeline && leakageAudit && <>
              <dl className="compact-definition">
                <dt>Split contract</dt><dd>{runSplitContract ? `${runSplitContract.family} · seed ${runSplitContract.split_seed}` : "Legacy / not linked to explicit contract"}</dd>
                {runSplitContract && <>
                  <dt>Exact source rows</dt><dd>Train {runSplitContract.role_source_rows.train.length} · validation {runSplitContract.role_source_rows.validation.length} · locked test {runSplitContract.role_source_rows.test.length}</dd>
                  <dt>Split identity</dt><dd><code>{runSplitContract.split_identity}</code></dd>
                </>}
                <dt>Transform fit scope</dt><dd>{transformPipeline.fit_role} only · {transformPipeline.steps.length} persisted step(s)</dd>
                <dt>Feature order</dt><dd>{transformPipeline.feature_order.join(", ") || "No features"}</dd>
                <dt>Preprocessing artifact</dt><dd><code>{transformPipeline.preprocessing_artifact_sha256}</code></dd>
                <dt>Leakage audit</dt><dd><StatusBadge tone={leakageAudit.status === "FAIL" ? "danger" : leakageAudit.status === "WARN" ? "warning" : "success"}>{leakageAudit.status}</StatusBadge> · {leakageAudit.rigor_profile} · {leakageAudit.findings.length} finding(s)</dd>
              </dl>
              <ol className="data-governance-steps">{transformPipeline.steps.map((step, index) => <li key={`${step.step_type}-${index}`}><strong>{step.step_type}</strong> · fit on {step.fit_role} · {step.input_columns.join(", ")} → {step.output_columns.join(", ")}</li>)}</ol>
              {leakageAudit.findings.length > 0 ? <ul className="data-governance-findings">{leakageAudit.findings.map((finding, index) => <li key={`${finding.code}-${index}`}><strong>{finding.severity.toUpperCase()} · {finding.code}</strong><span>{finding.remediation}</span></li>)}</ul> : <p>No structural leakage findings were recorded by this audit.</p>}
              <p className="scientific-note">{leakageAudit.scientific_note}</p>
            </>}
          </details>
          {study && <>
            <ChartSurface title={`Validation ${study.selection_metric} across seeds`} option={studyDistributionOption(study)} theme={theme} />
            <ChartSurface title="Validation-loss trajectories · epoch 0 included" option={studyTrajectoryOption(study)} theme={theme} />
            {statistics && <div className="run-summary-strip"><div><span>Mean</span><strong>{statistics.mean.toFixed(5)}</strong></div><div><span>Median</span><strong>{statistics.median.toFixed(5)}</strong></div><div><span>Std</span><strong>{statistics.std.toFixed(5)}</strong></div><div><span>Min / max</span><strong>{statistics.min.toFixed(5)} / {statistics.max.toFixed(5)}</strong></div></div>}
            <div className="info-message">{study.selection_reason}</div>
          </>}
          {run.model_kind === "decision_tree" && runCapabilitiesStatus === "loaded" && canExactTreePath && <section className="tree-path-panel">
            <span className="eyebrow">EXACT TREE EXECUTION PATH</span>
            <p>Structural execution evidence from the persisted declarative tree; it is not a post-hoc attribution.</p>
            {treeEvidenceStatus === "loading" && <p role="status">Checking saved tree-path evidence for this run…</p>}
            {treeEvidenceStatus === "none" && <p>No saved tree-path evidence exists yet for this project.</p>}
            {treeEvidenceStatus === "other_run" && <p>The latest saved tree path belongs to another run; it is not shown as evidence for this run.</p>}
            {treeEvidenceStatus === "error" && <div className="error" role="alert"><strong>Could not load saved tree-path evidence.</strong> {treeEvidenceError} <Button view="outlined" size="s" onClick={() => setTreeEvidenceReload((current) => current + 1)}>Retry tree-path check</Button></div>}
            <div className="training-config-grid">{run.feature_columns.map((column) => <label className="field-label" key={column}>{column}<input aria-label={`Tree input ${column}`} type="number" value={treeSample[column] ?? "0"} onChange={(event) => setTreeSample((current) => ({ ...current, [column]: event.target.value }))} /></label>)}</div>
            {treePathRecovery && <div className="error" role="alert" data-testid="tree-path-recovery"><strong>Tree-path save is uncertain; no duplicate was submitted.</strong><p>{treePathRecovery.error}</p><Button view="outlined" disabled={treePathRecovering} onClick={recoverTreePath}>Retry exact tree-path lookup</Button>{treePathRecovery.notFound && <Button view="outlined" disabled={treePathRecovering || running || project.read_only || run.run_id !== treePathRecovery.runId} onClick={explicitlyRepeatTreePath}>Explicitly repeat this exact trace</Button>}</div>}
            <Button view="outlined" disabled={running || !!treePathRecovery || project.read_only} onClick={traceTree} data-ruflex-action="tree_path.trace">Trace exact tree path</Button>
            {treeEvidence && <div className="info-message"><strong>{treeEvidence.label}</strong><br />{treeEvidence.steps.map((step) => `Node ${step.node_id}: ${step.feature_name} ≤ ${step.threshold.toFixed(4)} → ${step.decision.toUpperCase()}`).join(" · ")}<br />Leaf {treeEvidence.leaf_id} → prediction {treeEvidence.prediction.toFixed(5)}</div>}
          </section>}
          {run.model_kind === "random_forest" && <section className="tree-path-panel"><span className="eyebrow">ENSEMBLE STRUCTURAL EVIDENCE</span><h3>{String(run.model_spec.tree_count ?? "—")} persisted constituent trees</h3><p>The final forest prediction is an aggregation of all trees. RuFLEX deliberately does not present one tree path as an exact explanation of the ensemble.</p><dl className="compact-definition"><dt>Total nodes</dt><dd>{String(run.model_spec.node_count ?? "—")}</dd><dt>Maximum depth</dt><dd>{String(run.model_spec.max_depth ?? "—")}</dd><dt>Leaves</dt><dd>{String(run.model_spec.leaf_count ?? "—")}</dd><dt>Exact ensemble path</dt><dd>Not available</dd></dl></section>}
          {run.model_kind === "gradient_boosting" && <section className="tree-path-panel"><span className="eyebrow">STAGEWISE ENSEMBLE STRUCTURAL EVIDENCE</span><h3>{String(run.model_spec.tree_count ?? "—")} persisted boosting trees</h3><p>The prediction is a weighted stagewise aggregation. A single constituent-tree path is not an exact explanation of this ensemble.</p><dl className="compact-definition"><dt>Total nodes</dt><dd>{String(run.model_spec.node_count ?? "—")}</dd><dt>Maximum depth</dt><dd>{String(run.model_spec.max_depth ?? "—")}</dd><dt>Leaves</dt><dd>{String(run.model_spec.leaf_count ?? "—")}</dd><dt>Exact ensemble path</dt><dd>Not available</dd></dl></section>}
        </>}
      </section>
    </div>
    <section className="comparison-card"><span className="eyebrow">MODEL RUNTIME · DECLARED CAPABILITIES</span><div className="data-table-wrap"><table className="data-table"><thead><tr><th>model</th><th>family</th><th>available</th><th>capabilities</th><th>evidence boundary</th></tr></thead><tbody>{catalog.map((entry) => <tr key={entry.key}><td>{entry.display_name}</td><td>{entry.family}</td><td>{entry.available ? "available" : entry.unavailability_reason ?? "not available"}</td><td>{Object.entries(entry.capabilities).filter(([, value]) => value).map(([key]) => key).join(", ") || "—"}</td><td>{entry.limitations.join(" ") || "—"}</td></tr>)}</tbody></table></div></section>
    <StabilityLab project={project} study={study} theme={theme} onAnalysisChange={onStabilityAnalysisChange} onPolicyChange={onStabilityGatePolicyChange} />
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
