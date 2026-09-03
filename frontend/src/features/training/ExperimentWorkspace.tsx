import { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import { DatasetState, ModelCatalogEntry, ProjectSummary, StudyJob, TrainingRun, TrainingStudy, TreePathEvidence, studioApi } from "../../api";
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
  const [modelKind, setModelKind] = useState<"flat_neuro_fuzzy" | "logistic_regression" | "linear_regression" | "decision_tree" | "random_forest" | "gradient_boosting">("flat_neuro_fuzzy");
  const [maxEpochs, setMaxEpochs] = useState(20);
  const [learningRate, setLearningRate] = useState(0.01);
  const [batchSize, setBatchSize] = useState(32);
  const [patience, setPatience] = useState(8);
  const [maxRules, setMaxRules] = useState(8);
  const [seedList, setSeedList] = useState("42, 43, 44");
  const [studyMode, setStudyMode] = useState<"TRAINING_VARIABILITY" | "SPLIT_VARIABILITY" | "COMBINED_VARIABILITY">("TRAINING_VARIABILITY");
  const [splitSeed, setSplitSeed] = useState(42);
  const [study, setStudy] = useState<TrainingStudy | null>(restoredStudy);
  const [studyJob, setStudyJob] = useState<StudyJob | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeSample, setTreeSample] = useState<Record<string, string>>({});
  const [treeEvidence, setTreeEvidence] = useState<TreePathEvidence | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalogEntry[]>([]);
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
  useEffect(() => { studioApi.getModelCatalog().then(setCatalog).catch(() => setCatalog([])); }, []);
  useEffect(() => {
    studioApi.listStudyJobs(project.session_id).then((jobs) => {
      const resumable = jobs.filter((job) => ["QUEUED", "RUNNING"].includes(job.status)).at(-1);
      setStudyJob(resumable ?? null);
    }).catch(() => setStudyJob(null));
  }, [project.session_id]);

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
        model_kind: modelKind,
        seed,
        max_epochs: maxEpochs,
        learning_rate: learningRate,
        batch_size: batchSize,
        patience,
        validation_fraction: 0.2,
        test_fraction: 0.2,
        max_rules: maxRules,
      });
      onRun(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Training failed");
    } finally {
      setRunning(false);
    }
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
      let job = await studioApi.startStudyJob(project.session_id, { name: `Study ${new Date().toLocaleString()}`, model_kind: modelKind, seeds, randomness_protocol: studyMode, split_seed: splitSeed, training_seed: splitSeed, selection_metric: selectionMetric, max_epochs: maxEpochs, learning_rate: learningRate, batch_size: batchSize, patience, validation_fraction: .2, test_fraction: .2, max_rules: maxRules });
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
          <dt>Preprocessing</dt><dd>median fill + standardization fitted on train only</dd>
        </dl>
        <div className="training-config-grid">
          <label className="field-label">Model<select aria-label="Training model" value={modelKind} disabled={running || project.read_only} onChange={(event) => setModelKind(event.target.value as typeof modelKind)}><option value="flat_neuro_fuzzy">ANFIS / Flat neuro-fuzzy</option>{dataset.contract.task === "binary_classification" ? <option value="logistic_regression">Logistic regression baseline</option> : <option value="linear_regression">Linear regression baseline</option>}<option value="decision_tree">Decision Tree baseline</option><option value="random_forest">Random Forest baseline</option><option value="gradient_boosting">Gradient Boosting baseline</option></select></label>
          <NumberField label="Seed" value={seed} step={1} disabled={running || project.read_only} onChange={setSeed} />
          <NumberField label="Study split seed" value={splitSeed} step={1} disabled={running || project.read_only} onChange={setSplitSeed} />
          <NumberField label="Epochs" value={maxEpochs} min={1} max={2000} step={1} disabled={running || project.read_only} onChange={setMaxEpochs} />
          <NumberField label="Learning rate" value={learningRate} min={0.000001} max={1} step={0.001} disabled={running || project.read_only} onChange={setLearningRate} />
          <NumberField label="Batch size" value={batchSize} min={1} step={1} disabled={running || project.read_only} onChange={setBatchSize} />
          <NumberField label="Patience" value={patience} min={1} step={1} disabled={running || project.read_only} onChange={setPatience} />
          <NumberField label="Max rules / layer" value={maxRules} min={1} max={128} step={1} disabled={running || project.read_only} onChange={setMaxRules} />
          <label className="field-label">Study seeds<input aria-label="Study seeds" value={seedList} disabled={running || project.read_only} onChange={(event) => setSeedList(event.target.value)} /></label>
          <label className="field-label">Study randomness protocol<select aria-label="Study randomness protocol" value={studyMode} disabled={running || project.read_only} onChange={(event) => setStudyMode(event.target.value as typeof studyMode)}><option value="TRAINING_VARIABILITY">Training variability (fixed split)</option><option value="SPLIT_VARIABILITY">Split variability (fixed training seed)</option><option value="COMBINED_VARIABILITY">Combined variability</option></select></label>
        </div>
        <Button view="action" disabled={running || project.read_only} onClick={train}>{running ? "Training…" : "Run real training"}</Button>
        <Button view="outlined" disabled={running || project.read_only} onClick={trainStudy}>{running ? "Training…" : "Run multi-seed study"}</Button>
        {studyJob && <div className="info-message"><strong>Study job {studyJob.status}</strong> · LocalExecutor · {studyJob.seed_states.map((state) => `seed ${state.seed}: ${state.status}`).join(" · ")} {(["QUEUED", "RUNNING"].includes(studyJob.status)) && <><Button view="flat" size="s" onClick={resumeStudy}>Resume persisted study</Button><Button view="flat" size="s" onClick={cancelStudy}>Cancel study</Button></>} {studyJob.recovery_note && <small>{studyJob.recovery_note}</small>}</div>}
        <div className="info-message">Training variability fixes split membership and varies only model randomness. Split and combined modes are separate sensitivity protocols. Selection is validation-only and never reads the locked test split.</div>
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
            {run.preprocessing_artifact_sha256 && <><StatusBadge tone="success">train-only preprocessing persisted</StatusBadge><code>{run.preprocessing_artifact_sha256.slice(0, 24)}…</code></>}
            <span>seed {run.seed}</span>
            <span>{run.split.train_count}/{run.split.validation_count}/{run.split.test_count} rows</span>
          </div>
          {study && <>
            <ChartSurface title={`Validation ${study.selection_metric} across seeds`} option={studyDistributionOption(study)} theme={theme} />
            <ChartSurface title="Validation-loss trajectories · epoch 0 included" option={studyTrajectoryOption(study)} theme={theme} />
            {statistics && <div className="run-summary-strip"><div><span>Mean</span><strong>{statistics.mean.toFixed(5)}</strong></div><div><span>Median</span><strong>{statistics.median.toFixed(5)}</strong></div><div><span>Std</span><strong>{statistics.std.toFixed(5)}</strong></div><div><span>Min / max</span><strong>{statistics.min.toFixed(5)} / {statistics.max.toFixed(5)}</strong></div></div>}
            <div className="info-message">{study.selection_reason}</div>
          </>}
          {run.model_kind === "decision_tree" && <section className="tree-path-panel"><span className="eyebrow">EXACT TREE EXECUTION PATH</span><p>Structural execution evidence from the persisted declarative tree; it is not a post-hoc attribution.</p><div className="training-config-grid">{run.feature_columns.map((column) => <label className="field-label" key={column}>{column}<input aria-label={`Tree input ${column}`} type="number" value={treeSample[column] ?? "0"} onChange={(event) => setTreeSample((current) => ({ ...current, [column]: event.target.value }))} /></label>)}</div><Button view="outlined" disabled={running || project.read_only} onClick={traceTree}>Trace exact tree path</Button>{treeEvidence && <div className="info-message"><strong>{treeEvidence.label}</strong><br />{treeEvidence.steps.map((step) => `Node ${step.node_id}: ${step.feature_name} ≤ ${step.threshold.toFixed(4)} → ${step.decision.toUpperCase()}`).join(" · ")}<br />Leaf {treeEvidence.leaf_id} → prediction {treeEvidence.prediction.toFixed(5)}</div>}</section>}
          {run.model_kind === "random_forest" && <section className="tree-path-panel"><span className="eyebrow">ENSEMBLE STRUCTURAL EVIDENCE</span><h3>{String(run.model_spec.tree_count ?? "—")} persisted constituent trees</h3><p>The final forest prediction is an aggregation of all trees. RuFLEX deliberately does not present one tree path as an exact explanation of the ensemble.</p><dl className="compact-definition"><dt>Total nodes</dt><dd>{String(run.model_spec.node_count ?? "—")}</dd><dt>Maximum depth</dt><dd>{String(run.model_spec.max_depth ?? "—")}</dd><dt>Leaves</dt><dd>{String(run.model_spec.leaf_count ?? "—")}</dd><dt>Exact ensemble path</dt><dd>Not available</dd></dl></section>}
          {run.model_kind === "gradient_boosting" && <section className="tree-path-panel"><span className="eyebrow">STAGEWISE ENSEMBLE STRUCTURAL EVIDENCE</span><h3>{String(run.model_spec.tree_count ?? "—")} persisted boosting trees</h3><p>The prediction is a weighted stagewise aggregation. A single constituent-tree path is not an exact explanation of this ensemble.</p><dl className="compact-definition"><dt>Total nodes</dt><dd>{String(run.model_spec.node_count ?? "—")}</dd><dt>Maximum depth</dt><dd>{String(run.model_spec.max_depth ?? "—")}</dd><dt>Leaves</dt><dd>{String(run.model_spec.leaf_count ?? "—")}</dd><dt>Exact ensemble path</dt><dd>Not available</dd></dl></section>}
        </>}
      </section>
    </div>
    <section className="comparison-card"><span className="eyebrow">MODEL CATALOG · DECLARED CAPABILITIES</span><div className="data-table-wrap"><table className="data-table"><thead><tr><th>model</th><th>family</th><th>available</th><th>capabilities</th><th>evidence boundary</th></tr></thead><tbody>{catalog.map((entry) => <tr key={entry.key}><td>{entry.label}</td><td>{entry.family}</td><td>{entry.available ? "available" : "not available"}</td><td>{Object.entries(entry.capabilities).filter(([, value]) => value).map(([key]) => key).join(", ") || "—"}</td><td>{entry.limitation ?? "—"}</td></tr>)}</tbody></table></div></section>
    <StabilityLab project={project} study={study} theme={theme} />
    {error && <div className="error" role="alert">{error}</div>}
  </section>;
}
