import { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import { DatasetState, ExecutionBackendDescriptor, LeakageAuditReport, ModelCapabilityContract, ProjectSummary, RunCapabilityNegotiation, SplitContract, StudyJob, TrainingRun, TrainingStudy, TransformPipelineContract, TreePathEvidence, studioApi } from "../../api";
import { ChartSurface } from "../../charts/ChartSurface";
import { Button, EmptyState, StatusBadge } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";
import { StabilityLab } from "./StabilityLab";

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

export function ExperimentWorkspace({ project, dataset, run, study: restoredStudy, theme, onRun, onStudy }: {
  project: ProjectSummary;
  dataset: DatasetState | null;
  run: TrainingRun | null;
  study: TrainingStudy | null;
  theme: StudioTheme;
  onRun: (run: TrainingRun) => void;
  onStudy: (study: TrainingStudy) => void;
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
  const [splitEvidenceError, setSplitEvidenceError] = useState<string | null>(null);
  const [study, setStudy] = useState<TrainingStudy | null>(restoredStudy);
  const [studyJob, setStudyJob] = useState<StudyJob | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeSample, setTreeSample] = useState<Record<string, string>>({});
  const [treeEvidence, setTreeEvidence] = useState<TreePathEvidence | null>(null);
  const [transformPipeline, setTransformPipeline] = useState<TransformPipelineContract | null>(null);
  const [leakageAudit, setLeakageAudit] = useState<LeakageAuditReport | null>(null);
  const [runSplitContract, setRunSplitContract] = useState<SplitContract | null>(null);
  const [dataEvidenceState, setDataEvidenceState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [catalog, setCatalog] = useState<ModelCapabilityContract[]>([]);
  const [executionBackends, setExecutionBackends] = useState<ExecutionBackendDescriptor[]>([]);
  const [executionBackendKey, setExecutionBackendKey] = useState("local_executor");
  const [runCapabilities, setRunCapabilities] = useState<RunCapabilityNegotiation | null>(null);
  const option = useMemo(() => run ? trajectoryOption(run) : null, [run]);
  const statistics = useMemo(() => study ? studyStatistics(study) : null, [study]);
  useEffect(() => {
    setStudy(restoredStudy);
  }, [restoredStudy?.study_id]);
  useEffect(() => {
    if (!run || run.model_kind !== "decision_tree") { setTreeEvidence(null); return; }
    studioApi.getLatestTreePath(project.session_id).then((evidence) => {
      setTreeEvidence(evidence.run_id === run.run_id ? evidence : null);
    }).catch(() => setTreeEvidence(null));
  }, [project.session_id, run?.run_id, run?.model_kind]);
  useEffect(() => {
    let active = true;
    setTransformPipeline(null);
    setLeakageAudit(null);
    setRunSplitContract(null);
    if (!run?.transform_pipeline_id || !run.leakage_audit_id) {
      setDataEvidenceState("idle");
      return () => { active = false; };
    }
    setDataEvidenceState("loading");
    Promise.all([
      studioApi.getTransformPipeline(project.session_id, run.transform_pipeline_id),
      studioApi.getLeakageAudit(project.session_id, run.leakage_audit_id),
      run.split.split_contract_id ? studioApi.getSplitContract(project.session_id, run.split.split_contract_id) : Promise.resolve(null),
    ]).then(([pipeline, audit, frozenSplit]) => {
      if (!active) return;
      if (pipeline.pipeline_id !== run.transform_pipeline_id || audit.audit_id !== run.leakage_audit_id || pipeline.dataset_fingerprint !== dataset?.contract.dataset_fingerprint || audit.dataset_fingerprint !== pipeline.dataset_fingerprint || pipeline.split_contract_id !== (frozenSplit?.split_id ?? null) || audit.split_contract_id !== (frozenSplit?.split_id ?? null) || audit.transform_pipeline_id !== pipeline.pipeline_id) throw new Error("Persisted data evidence identity does not match the selected run.");
      setTransformPipeline(pipeline);
      setLeakageAudit(audit);
      setRunSplitContract(frozenSplit);
      setDataEvidenceState("loaded");
    }).catch(() => {
      if (active) setDataEvidenceState("error");
    });
    return () => { active = false; };
  }, [project.session_id, dataset?.contract.dataset_fingerprint, run?.run_id, run?.transform_pipeline_id, run?.leakage_audit_id, run?.split.split_contract_id]);
  useEffect(() => {
    let active = true;
    setSplitEvidenceError(null);
    studioApi.listSplitContracts(project.session_id).then((contracts) => {
      if (!active) return;
      const current = contracts.at(-1) ?? null;
      setSplitContract(current);
      if (current) { setSplitFamily(current.family); setGroupColumn(current.group_column ?? current.time_column ?? current.site_column ?? current.device_column ?? current.spatial_column ?? current.regime_column ?? ""); setSplitSeed(current.split_seed); }
    }).catch((reason) => {
      if (!active) return;
      setSplitContract(null);
      setSplitEvidenceError(reason instanceof Error ? reason.message : "Saved split provenance could not be verified.");
    });
    return () => { active = false; };
  }, [project.session_id]);
  useEffect(() => {
    if (!run) { setRunCapabilities(null); return; }
    studioApi.getTrainingRunCapabilities(project.session_id, run.run_id).then(setRunCapabilities).catch(() => setRunCapabilities(null));
  }, [project.session_id, run?.run_id]);
  useEffect(() => { studioApi.getModels().then(setCatalog).catch(() => setCatalog([])); }, []);
  useEffect(() => { studioApi.getRuntimeBackends().then((backends) => {
    setExecutionBackends(backends);
    if (!backends.some((backend) => backend.identity.key === executionBackendKey)) setExecutionBackendKey(backends[0]?.identity.key ?? "local_executor");
  }).catch(() => setExecutionBackends([])); }, []);
  const datasetTask = dataset?.contract.task;
  const compatibleModels = useMemo(() => catalog.filter((entry) => entry.available && entry.capabilities.fit && !!datasetTask && entry.supported_tasks.includes(datasetTask)), [catalog, datasetTask]);
  const selectedModel = compatibleModels.find((entry) => entry.training_model_kinds.includes(modelKind)) ?? null;
  const selectedAdapterKey = selectedModel?.provider === "ruflex.builtin" ? null : selectedModel?.key ?? null;
  const supportsParameter = (name: string) => Boolean(selectedModel?.parameter_constraints[name]);
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
    studioApi.listStudyJobs(project.session_id).then((jobs) => {
      if (!active) return;
      const latest = [...jobs].reverse();
      const resumable = latest.find((job) => ["QUEUED", "RUNNING"].includes(job.status));
      const restoredStudyJob = restoredStudy
        ? latest.find((job) => job.study_id === restoredStudy.study_id)
        : undefined;
      setStudyJob(resumable ?? restoredStudyJob ?? latest[0] ?? null);
    }).catch(() => { if (active) setStudyJob(null); });
    return () => { active = false; };
  }, [project.session_id, restoredStudy?.study_id]);

  async function observeStudy(initial: StudyJob) {
    let job = initial;
    setStudyJob(job);
    while (["QUEUED", "RUNNING"].includes(job.status)) {
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      job = await studioApi.getStudyJob(project.session_id, job.job_id);
      setStudyJob(job);
    }
    if (job.status !== "SUCCEEDED") throw new Error(job.error ?? `Study ${job.status.toLowerCase()}`);
    const result = await studioApi.getLatestTrainingStudy(project.session_id);
    setStudy(result); onStudy(result);
    const selected = result.seed_runs.find((item) => item.run_id === result.selected_run_id);
    if (selected) onRun(selected);
  }

  async function train() {
    setRunning(true);
    setError(null);
    try {
      const result = await studioApi.runTraining(project.session_id, {
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
      });
      onRun(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Training failed");
    } finally {
      setRunning(false);
    }
  }
  async function freezeSplitContract() {
    setRunning(true); setError(null);
    try {
      if (splitFamily !== "RANDOM" && !groupColumn) throw new Error("Choose the declared identity column before freezing this split.");
      const identity = splitFamily === "GROUP" ? { group_column: groupColumn } : splitFamily === "TEMPORAL" ? { time_column: groupColumn } : splitFamily === "SITE_HOLDOUT" ? { site_column: groupColumn } : splitFamily === "DEVICE_HOLDOUT" ? { device_column: groupColumn } : splitFamily === "SPATIAL" ? { spatial_column: groupColumn } : splitFamily === "REGIME" ? { regime_column: groupColumn } : {};
      const created = await studioApi.createSplitContract(project.session_id, { family: splitFamily, split_seed: splitSeed, validation_fraction: .2, test_fraction: .2, ...identity });
      setSplitContract(created);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not freeze split contract"); }
    finally { setRunning(false); }
  }
  async function trainStudy() {
    const seeds = [...new Set(seedList.split(",").map((value) => Number(value.trim())).filter(Number.isInteger))];
    if (seeds.length < 3) {
      setError("Enter at least three distinct integer seeds.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const selectionMetric = dataset?.contract.task === "regression" ? "rmse" : "f1";
      if (splitContract && studyMode !== "TRAINING_VARIABILITY") throw new Error("A frozen SplitContract can be used only with fixed-split training variability studies.");
      let job = await studioApi.startStudyJob(project.session_id, { name: `Study ${new Date().toLocaleString()}`, model_kind: trainingModelKind, adapter_key: selectedAdapterKey, seeds, randomness_protocol: studyMode, split_seed: splitContract?.split_seed ?? splitSeed, training_seed: splitSeed, split_contract_id: splitContract?.split_id ?? null, execution_backend_key: executionBackendKey, selection_metric: selectionMetric, max_epochs: maxEpochs, learning_rate: learningRate, batch_size: batchSize, patience, validation_fraction: .2, test_fraction: .2, max_rules: maxRules, n_estimators: nEstimators, max_depth: maxDepth });
      await observeStudy(job);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Multi-seed study failed");
    } finally {
      setRunning(false);
    }
  }
  async function traceTree() {
    if (!run) return;
    const sample = Object.fromEntries(run.feature_columns.map((column) => [column, Number(treeSample[column])])) as Record<string, number>;
    if (Object.values(sample).some((value) => !Number.isFinite(value))) {
      setError("Enter a finite value for every tree feature.");
      return;
    }
    setRunning(true); setError(null);
    try { setTreeEvidence(await studioApi.createTreePath(project.session_id, run.run_id, sample)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Tree path trace failed"); }
    finally { setRunning(false); }
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

  if (!dataset) return <section className="feature-workspace"><EmptyState title="No confirmed dataset">Confirm a DatasetContract in Data before training a model.</EmptyState></section>;

  return <section className="feature-workspace training-workspace">
    <div className="feature-toolbar">
      <div><span className="eyebrow">REAL TRAINING ENGINE</span><h2>Train a model revision</h2><p>Canonical train-only preprocessing · held-out test remains locked.</p></div>
      <StatusBadge tone={running ? "warning" : run ? "success" : "info"}>{running ? "Training" : run ? "Completed run" : "Ready"}</StatusBadge>
    </div>

    <div className="training-grid">
      <section className="training-config-panel">
        <h3>Protocol</h3>
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
          {supportsParameter("max_epochs") && <NumberField label="Epochs" value={maxEpochs} min={1} max={2000} step={1} disabled={running || project.read_only} onChange={setMaxEpochs} />}
          {supportsParameter("learning_rate") && <NumberField label="Learning rate" value={learningRate} min={0.000001} max={1} step={0.001} disabled={running || project.read_only} onChange={setLearningRate} />}
          {supportsParameter("batch_size") && <NumberField label="Batch size" value={batchSize} min={1} step={1} disabled={running || project.read_only} onChange={setBatchSize} />}
          {supportsParameter("patience") && <NumberField label="Patience" value={patience} min={1} step={1} disabled={running || project.read_only} onChange={setPatience} />}
          {supportsParameter("max_rules") && <NumberField label="Max rules / layer" value={maxRules} min={1} max={128} step={1} disabled={running || project.read_only} onChange={setMaxRules} />}
          {supportsParameter("n_estimators") && <NumberField label="Trees / estimators" value={nEstimators} min={1} step={1} disabled={running || project.read_only} onChange={setNEstimators} />}
          {supportsParameter("max_depth") && <label className="field-label">Maximum depth<input aria-label="Maximum depth" type="number" min={1} value={maxDepth ?? ""} placeholder="unlimited" disabled={running || project.read_only} onChange={(event) => setMaxDepth(event.target.value === "" ? null : Number(event.target.value))} /></label>}
          <label className="field-label">Study seeds<input aria-label="Study seeds" value={seedList} disabled={running || project.read_only} onChange={(event) => setSeedList(event.target.value)} /></label>
          <label className="field-label">Study randomness protocol<select aria-label="Study randomness protocol" value={studyMode} disabled={running || project.read_only} onChange={(event) => setStudyMode(event.target.value as typeof studyMode)}><option value="TRAINING_VARIABILITY">Training variability (fixed split)</option><option value="SPLIT_VARIABILITY">Split variability (fixed training seed)</option><option value="COMBINED_VARIABILITY">Combined variability</option></select></label>
          <label className="field-label">Study execution backend<select aria-label="Study execution backend" value={executionBackendKey} disabled={running || project.read_only || !executionBackends.length} onChange={(event) => setExecutionBackendKey(event.target.value)}>{executionBackends.map((backend) => <option key={backend.identity.key} value={backend.identity.key}>{backend.identity.key} · {backend.identity.provider}</option>)}</select></label>
        </div>
        <Button view="outlined" disabled={running || project.read_only || Boolean(splitEvidenceError)} onClick={freezeSplitContract} data-ruflex-action="split.freeze">Freeze {splitFamily} SplitContract</Button>
        <Button view="action" disabled={running || project.read_only || Boolean(splitEvidenceError)} onClick={train} data-ruflex-action="training.run">{running ? "Training…" : "Run real training"}</Button>
        <Button view="outlined" disabled={running || project.read_only || Boolean(splitEvidenceError)} onClick={trainStudy} data-ruflex-action="study.start">{running ? "Training…" : "Run multi-seed study"}</Button>
        {studyJob && <div className="info-message"><strong>Study job {studyJob.status}</strong> · {studyJob.execution_backend_key ?? studyJob.execution_backend} · {studyJob.seed_states.map((state) => `seed ${state.seed}: ${state.status}`).join(" · ")} {(["QUEUED", "RUNNING"].includes(studyJob.status)) && <><Button view="flat" size="s" onClick={resumeStudy} data-ruflex-action="study.resume">Resume persisted study</Button><Button view="flat" size="s" onClick={cancelStudy} data-ruflex-action="study.cancel">Cancel study</Button></>} {studyJob.recovery_note && <small>{studyJob.recovery_note}</small>}</div>}
        <div className="info-message">A frozen SplitContract assigns exact source rows before fitting. GROUP keeps each declared identity in one role. It makes split membership auditable; it does not by itself establish generalization validity.</div>
        {splitEvidenceError && <div className="error" role="alert">Saved split provenance is invalid or unavailable. Training is blocked rather than falling back to an unverified split. {splitEvidenceError}</div>}
        {project.read_only && <div className="info-message">Read-only projects cannot start training runs.</div>}
      </section>

      <section className="training-result-panel">
        {!run || !option ? <EmptyState title="No training run yet">Start a run to produce an actual model artifact and training trajectory.</EmptyState> : <>
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
            {dataEvidenceState === "error" && <p className="error" role="alert">Could not reopen this run’s data-governance evidence. The saved run references are not being treated as verified.</p>}
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
          {canExactTreePath && <section className="tree-path-panel"><span className="eyebrow">EXACT TREE EXECUTION PATH</span><p>Structural execution evidence from the persisted declarative tree; it is not a post-hoc attribution.</p><div className="training-config-grid">{run.feature_columns.map((column) => <label className="field-label" key={column}>{column}<input aria-label={`Tree input ${column}`} type="number" value={treeSample[column] ?? "0"} onChange={(event) => setTreeSample((current) => ({ ...current, [column]: event.target.value }))} /></label>)}</div><Button view="outlined" disabled={running || project.read_only} onClick={traceTree} data-ruflex-action="tree_path.trace">Trace exact tree path</Button>{treeEvidence && <div className="info-message"><strong>{treeEvidence.label}</strong><br />{treeEvidence.steps.map((step) => `Node ${step.node_id}: ${step.feature_name} ≤ ${step.threshold.toFixed(4)} → ${step.decision.toUpperCase()}`).join(" · ")}<br />Leaf {treeEvidence.leaf_id} → prediction {treeEvidence.prediction.toFixed(5)}</div>}</section>}
          {run.model_kind === "random_forest" && <section className="tree-path-panel"><span className="eyebrow">ENSEMBLE STRUCTURAL EVIDENCE</span><h3>{String(run.model_spec.tree_count ?? "—")} persisted constituent trees</h3><p>The final forest prediction is an aggregation of all trees. RuFLEX deliberately does not present one tree path as an exact explanation of the ensemble.</p><dl className="compact-definition"><dt>Total nodes</dt><dd>{String(run.model_spec.node_count ?? "—")}</dd><dt>Maximum depth</dt><dd>{String(run.model_spec.max_depth ?? "—")}</dd><dt>Leaves</dt><dd>{String(run.model_spec.leaf_count ?? "—")}</dd><dt>Exact ensemble path</dt><dd>Not available</dd></dl></section>}
          {run.model_kind === "gradient_boosting" && <section className="tree-path-panel"><span className="eyebrow">STAGEWISE ENSEMBLE STRUCTURAL EVIDENCE</span><h3>{String(run.model_spec.tree_count ?? "—")} persisted boosting trees</h3><p>The prediction is a weighted stagewise aggregation. A single constituent-tree path is not an exact explanation of this ensemble.</p><dl className="compact-definition"><dt>Total nodes</dt><dd>{String(run.model_spec.node_count ?? "—")}</dd><dt>Maximum depth</dt><dd>{String(run.model_spec.max_depth ?? "—")}</dd><dt>Leaves</dt><dd>{String(run.model_spec.leaf_count ?? "—")}</dd><dt>Exact ensemble path</dt><dd>Not available</dd></dl></section>}
        </>}
      </section>
    </div>
    <section className="comparison-card"><span className="eyebrow">MODEL RUNTIME · DECLARED CAPABILITIES</span><div className="data-table-wrap"><table className="data-table"><thead><tr><th>model</th><th>family</th><th>available</th><th>capabilities</th><th>evidence boundary</th></tr></thead><tbody>{catalog.map((entry) => <tr key={entry.key}><td>{entry.display_name}</td><td>{entry.family}</td><td>{entry.available ? "available" : entry.unavailability_reason ?? "not available"}</td><td>{Object.entries(entry.capabilities).filter(([, value]) => value).map(([key]) => key).join(", ") || "—"}</td><td>{entry.limitations.join(" ") || "—"}</td></tr>)}</tbody></table></div></section>
    <StabilityLab project={project} study={study} theme={theme} />
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
