import { useEffect, useMemo, useState } from "react";
import {
  DatasetState,
  BehaviorSpec,
  BehaviorSpecResult,
  ExplanationReproducibilityAnalysis,
  ExhaustiveLabResult,
  AssuranceCase,
  ConditionMonitoringDemo,
  GeneralizationResponse,
  ExplanationCheck,
  ExplanationContract,
  VerificationBundleValidation,
  FISEvaluation,
  ModelCatalogEntry,
  ProductJob,
  ProjectSummary,
  TrainingRun,
  TreePathEvidence,
  studioApi,
} from "../../api";
import { Button, EmptyState, StatusBadge, TextInput } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";
import { TraceWorkspace } from "../modelbuild/TraceWorkspace";

function statusTone(status: ExplanationCheck["status"] | ExplanationCheck["checks"][number]["status"]) {
  if (status === "FAILED" || status === "FAIL") return "danger" as const;
  if (status === "WARNING" || status === "WARN") return "warning" as const;
  if (status === "N/A") return "info" as const;
  return "success" as const;
}

export function EvidenceWorkspace({
  project,
  dataset,
  run,
  evaluation,
  previousEvaluation,
  treeEvidence,
  explanation,
  explanationCheck,
  behaviorResult: restoredBehaviorResult,
  reproducibility: restoredReproducibility,
  exhaustive: restoredExhaustive,
  assurance: restoredAssurance,
  selectivePolicy,
  generalization,
  theme,
  onExplanation,
  onExplanationCheck,
  onBehaviorResult,
  onReproducibility,
  onExhaustive,
  onAssurance,
}: {
  project: ProjectSummary;
  dataset: DatasetState | null;
  run: TrainingRun | null;
  evaluation: FISEvaluation | null;
  previousEvaluation: FISEvaluation | null;
  treeEvidence: TreePathEvidence | null;
  explanation: ExplanationContract | null;
  explanationCheck: ExplanationCheck | null;
  behaviorResult: BehaviorSpecResult | null;
  reproducibility: ExplanationReproducibilityAnalysis | null;
  exhaustive: ExhaustiveLabResult | null;
  assurance: AssuranceCase | null;
  selectivePolicy: import("../../api").SelectivePredictionPolicy | null;
  generalization: GeneralizationResponse | null;
  theme: StudioTheme;
  onExplanation: (value: ExplanationContract | null) => void;
  onExplanationCheck: (value: ExplanationCheck | null) => void;
  onBehaviorResult: (value: BehaviorSpecResult | null) => void;
  onReproducibility: (value: ExplanationReproducibilityAnalysis | null) => void;
  onExhaustive: (value: ExhaustiveLabResult | null) => void;
  onAssurance: (value: AssuranceCase | null) => void;
}) {
  const initialSample = useMemo(() => {
    if (!run) return {} as Record<string, string>;
    const preview = dataset?.preview?.[0] ?? {};
    const result: Record<string, string> = {};
    for (const feature of run.feature_columns) {
      const value = preview[feature];
      result[feature] = typeof value === "number" ? String(value) : "0";
    }
    return result;
  }, [dataset, run?.run_id]);
  const [sample, setSample] = useState<Record<string, string>>(initialSample);
  const [comparisonSample, setComparisonSample] = useState<Record<string, string>>(initialSample);
  type EvidenceMethod = "occlusion" | "integrated_gradients" | "gradient_shap" | "shap" | "tree_shap";
  const [method, setMethod] = useState<EvidenceMethod>("occlusion");
  const [catalog, setCatalog] = useState<ModelCatalogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [behaviorKind, setBehaviorKind] = useState<BehaviorSpec["kind"]>("output_range");
  const [behaviorName, setBehaviorName] = useState("Output remains in declared range");
  const [minimum, setMinimum] = useState("0");
  const [maximum, setMaximum] = useState("1");
  const [direction, setDirection] = useState<"nondecreasing" | "nonincreasing">("nondecreasing");
  const [behaviorSpec, setBehaviorSpec] = useState<BehaviorSpec | null>(null);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorSpecResult | null>(restoredBehaviorResult);
  const [reproducibility, setReproducibility] = useState<ExplanationReproducibilityAnalysis | null>(restoredReproducibility);
  const [persistedExplanations, setPersistedExplanations] = useState<ExplanationContract[]>([]);
  const [selectedExplanationIds, setSelectedExplanationIds] = useState<string[]>([]);
  const [exhaustive, setExhaustive] = useState<ExhaustiveLabResult | null>(restoredExhaustive);
  const [gridPoints, setGridPoints] = useState("3");
  const [assurance, setAssurance] = useState<AssuranceCase | null>(restoredAssurance);
  const [bundle, setBundle] = useState<{ path: string; sha256: string; entry_count: number } | null>(null);
  const [bundleValidation, setBundleValidation] = useState<VerificationBundleValidation | null>(null);
  const [demo, setDemo] = useState<ConditionMonitoringDemo | null>(null);
  const [explanationJob, setExplanationJob] = useState<ProductJob | null>(null);

  useEffect(() => { setSample(initialSample); setComparisonSample(initialSample); }, [initialSample]);
  useEffect(() => setBehaviorResult(restoredBehaviorResult), [restoredBehaviorResult?.result_id]);
  useEffect(() => setReproducibility(restoredReproducibility), [restoredReproducibility?.analysis_id]);
  useEffect(() => setExhaustive(restoredExhaustive), [restoredExhaustive?.result_id]);
  useEffect(() => setAssurance(restoredAssurance), [restoredAssurance?.assurance_id]);
  useEffect(() => { studioApi.getLatestConditionMonitoringDemo(project.session_id).then(setDemo).catch(() => setDemo(null)); }, [project.session_id]);
  useEffect(() => { studioApi.listPosthocExplanationJobs(project.session_id).then((jobs) => setExplanationJob(jobs[0] ?? null)).catch(() => setExplanationJob(null)); }, [project.session_id]);
  useEffect(() => { if (project) studioApi.listExplanations(project.session_id).then(setPersistedExplanations).catch(() => setPersistedExplanations([])); }, [project.session_id, explanation?.explanation_id]);
  useEffect(() => {
    studioApi.getModelCatalog().then(setCatalog).catch(() => setCatalog([]));
  }, []);
  const modelCapabilities = useMemo(() => {
    if (!run) return {} as Record<string, boolean>;
    const key = run.model_kind === "logistic_regression" || run.model_kind === "linear_regression" ? "linear" : run.model_kind;
    return catalog.find((entry) => entry.key === key)?.capabilities ?? {};
  }, [catalog, run?.model_kind]);
  const availableMethods = useMemo(() => {
    const methods: EvidenceMethod[] = [];
    if (modelCapabilities.occlusion) methods.push("occlusion");
    if (modelCapabilities.shap) methods.push("shap");
    if (modelCapabilities.tree_shap) methods.push("tree_shap");
    if (modelCapabilities.integrated_gradients) methods.push("integrated_gradients");
    if (modelCapabilities.gradient_shap) methods.push("gradient_shap");
    return methods;
  }, [modelCapabilities]);
  useEffect(() => {
    if (!run || availableMethods.length === 0) return;
    if (!availableMethods.includes(method)) setMethod(availableMethods[0]);
  }, [run?.run_id, availableMethods, method]);

  function numericSample() {
    if (!run) throw new Error("Select a trained model run first.");
    const result: Record<string, number> = {};
    for (const feature of run.feature_columns) {
      const value = Number(sample[feature]);
      if (!Number.isFinite(value)) throw new Error(`${feature} must be a finite number.`);
      result[feature] = value;
    }
    return result;
  }

  function numericComparisonSample() {
    if (!run) throw new Error("Select a trained model run first.");
    const result: Record<string, number> = {};
    for (const feature of run.feature_columns) {
      const value = Number(comparisonSample[feature]);
      if (!Number.isFinite(value)) throw new Error(`Comparison ${feature} must be a finite number.`);
      result[feature] = value;
    }
    return result;
  }

  async function runConditionDemo() {
    if (!selectivePolicy) { setError("Create a validation-derived selective policy before running the condition-monitoring demo."); return; }
    setBusy(true); setError(null);
    try { setDemo(await studioApi.runConditionMonitoringDemo(project.session_id, numericSample(), selectivePolicy.policy_id, generalization?.contract.contract_id ?? null)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function generate() {
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      let job = await studioApi.startPosthocExplanationJob(project.session_id, run.run_id, numericSample(), method);
      setExplanationJob(job);
      for (let attempt = 0; attempt < 120 && ["queued", "running"].includes(job.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
        job = await studioApi.getPosthocExplanationJob(project.session_id, job.job_id);
        setExplanationJob(job);
      }
      if (job.status !== "succeeded" || !job.output.explanation_id) throw new Error(job.error ?? job.message ?? "Explanation job did not complete.");
      onExplanation(await studioApi.getExplanation(project.session_id, job.output.explanation_id));
      onExplanationCheck(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function check() {
    if (!explanation) return;
    setBusy(true);
    setError(null);
    try {
      let job = await studioApi.startExplanationCheckJob(project.session_id, explanation.explanation_id);
      setExplanationJob(job);
      for (let attempt = 0; attempt < 120 && ["queued", "running"].includes(job.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
        job = await studioApi.getPosthocExplanationJob(project.session_id, job.job_id);
        setExplanationJob(job);
      }
      if (job.status !== "succeeded" || !job.output.check_id) throw new Error(job.error ?? job.message ?? "Explanation-check job did not complete.");
      onExplanationCheck(await studioApi.getExplanationCheck(project.session_id, job.output.check_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function createAndRunBehavior() {
    if (!run) return;
    setBusy(true); setError(null);
    try {
      const numeric = numericSample();
      const pair = behaviorKind === "output_range" || behaviorKind === "regression_case" ? null : numericComparisonSample();
      const created = await studioApi.createBehaviorSpec(project.session_id, {
        run_id: run.run_id, name: behaviorName, kind: behaviorKind, sample: numeric, comparison_sample: pair,
        minimum: behaviorKind === "invariance_pair" || behaviorKind === "monotonic_pair" ? null : Number(minimum),
        maximum: behaviorKind === "invariance_pair" || behaviorKind === "monotonic_pair" ? null : Number(maximum),
        expected_direction: behaviorKind === "monotonic_pair" ? direction : null,
        tolerance: 1e-9, rationale: "Persisted engineering behavior requirement.",
      });
      setBehaviorSpec(created); const result = await studioApi.runBehaviorSpec(project.session_id, created.spec_id); setBehaviorResult(result); onBehaviorResult(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function compareReproducibility() {
    setBusy(true); setError(null);
    try {
      const result = await studioApi.createExplanationReproducibility(project.session_id, selectedExplanationIds);
      setReproducibility(result); onReproducibility(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function runExhaustive(kind: ExhaustiveLabResult["kind"]) {
    setBusy(true); setError(null);
    try { const result=await studioApi.runExhaustiveLab(project.session_id, kind, kind === "decision_tree_structure" ? run?.run_id ?? null : null, Number(gridPoints)); setExhaustive(result); onExhaustive(result); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function waitForJob(job: ProductJob) {
    for (let attempt = 0; attempt < 120 && ["queued", "running"].includes(job.status); attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
      job = await studioApi.getPosthocExplanationJob(project.session_id, job.job_id);
      setExplanationJob(job);
    }
    if (job.status !== "succeeded") throw new Error(job.error ?? job.message ?? "Evidence job did not complete.");
    return job;
  }
  async function buildAssurance() { setBusy(true); setError(null); try { const job = await waitForJob(await studioApi.startAssuranceCaseJob(project.session_id)); const result=await studioApi.getLatestAssuranceCase(project.session_id); if (!job.output.assurance_id || result.assurance_id !== job.output.assurance_id) throw new Error("Assurance job output identity did not match its persisted AssuranceCase."); setAssurance(result); onAssurance(result); } catch(reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(false); } }
  async function exportBundle() { setBusy(true); setError(null); try { const job = await waitForJob(await studioApi.startVerificationBundleJob(project.session_id)); const exported={ path: job.output.path, sha256: job.output.sha256, entry_count: Number(job.output.entry_count) }; if (!exported.path || !exported.sha256 || !Number.isFinite(exported.entry_count)) throw new Error("VerificationBundle job did not persist a complete export receipt."); setBundle(exported); setBundleValidation(await studioApi.validateVerificationBundle(exported.path)); } catch(reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(false); } }

  const hasExact = Boolean(evaluation || treeEvidence);

  return (
    <section className="evidence-workbench">
      <div className="feature-toolbar">
        <div>
          <span className="eyebrow">EVIDENCE WORKBENCH</span>
          <h2>Computation evidence and post-hoc attribution</h2>
          <p>Exact computation, structural execution and post-hoc attribution remain separate scientific objects.</p>
        </div>
        <div className="evidence-label-row">
          {evaluation && <StatusBadge tone="success">EXACT COMPUTATION</StatusBadge>}
          {treeEvidence && <StatusBadge tone="success">STRUCTURAL TRACE</StatusBadge>}
          {explanation && <StatusBadge tone="warning">POST-HOC ATTRIBUTION</StatusBadge>}
        </div>
      </div>

      {hasExact && (
        <section className="evidence-section">
          <TraceWorkspace evaluation={evaluation} previousEvaluation={previousEvaluation} treeEvidence={treeEvidence} theme={theme} />
        </section>
      )}

      <section className="evidence-section posthoc-panel">
        <div className="feature-toolbar compact-toolbar">
          <div>
            <span className="eyebrow">POST-HOC ATTRIBUTION</span>
            <h3>{method === "occlusion" ? "Train-reference occlusion" : method === "integrated_gradients" ? "Integrated Gradients" : method === "gradient_shap" ? "GradientSHAP" : method === "tree_shap" ? "TreeSHAP" : "SHAP · permutation"}</h3>
            <p>{method === "occlusion" ? "One feature at a time is replaced by its train-derived reference." : method === "integrated_gradients" ? "Gradients are integrated from a train-derived reference to the observed sample." : method === "gradient_shap" ? "Expected gradients use a deterministic train-only background." : method === "tree_shap" ? "TreeSHAP uses the persisted declarative tree ensemble and a deterministic train-only background." : "Permutation SHAP uses the persisted model through a deterministic train-only background."} This is not a causal effect or an exact trace.</p>
          </div>
          <StatusBadge tone="warning">post-hoc</StatusBadge>
        </div>
        {!run ? (
          <EmptyState title="No trained model selected">Train or reopen a catalog model to generate a local attribution.</EmptyState>
        ) : (
          <>
            <label className="field-label evidence-method-select">Method
              <select aria-label="Explanation method" value={method} onChange={(event) => setMethod(event.target.value as EvidenceMethod)}>
                {availableMethods.map((candidate) => <option value={candidate} key={candidate}>{candidate === "occlusion" ? "Occlusion" : candidate === "shap" ? "SHAP · permutation" : candidate === "tree_shap" ? "TreeSHAP" : candidate === "integrated_gradients" ? "Integrated Gradients" : "GradientSHAP"}</option>)}
              </select>
            </label>
            <div className="evidence-sample-grid">
              {run.feature_columns.map((feature) => (
                <label className="field-label" key={feature}>
                  {feature}
                  <TextInput
                    aria-label={`Evidence ${feature}`}
                    value={sample[feature] ?? ""}
                    onUpdate={(value) => setSample((current) => ({ ...current, [feature]: value }))}
                  />
                </label>
              ))}
            </div>
            <div className="evidence-actions">
              <Button view="action" disabled={busy || project.read_only || availableMethods.length === 0} onClick={generate}>{busy ? "Generating…" : "Generate explanation"}</Button>
              <span className="property-description">{run.model_kind} · run {run.run_id.slice(0, 8)}</span>
            </div>
            {explanationJob && <div className="property-description" data-testid="explanation-job"><StatusBadge tone={explanationJob.status === "succeeded" ? "success" : explanationJob.status === "failed" ? "danger" : "warning"}>{explanationJob.status.toUpperCase()}</StatusBadge> LocalExecutor · {explanationJob.message ?? "Persisted operation"}{explanationJob.error && ` · ${explanationJob.error}`}</div>}
          </>
        )}
        {error && <div className="error" role="alert">{error}</div>}
        {explanation && (
          <div className="evidence-result-grid">
            <section className="trace-card">
              <strong>Explanation contract</strong>
              <div><span>Category</span><code>{explanation.epistemic_category}</code></div>
              <div><span>Method</span><code>{explanation.method}</code></div>
              <div><span>Explained output</span><code>{explanation.prediction.toFixed(6)}</code></div>
              <div><span>Output space</span><code>{explanation.output_space}</code></div>
              {explanation.preprocessing_identity && <div><span>Preprocessing</span><code>{explanation.preprocessing_identity.slice(0, 28)}…</code></div>}
              {explanation.sample_identity && <div><span>Sample identity</span><code>{explanation.sample_identity.slice(0, 28)}…</code></div>}
              {explanation.base_value !== null && <div><span>Base value</span><code>{explanation.base_value.toFixed(6)}</code></div>}
              {explanation.completeness_error !== null && <div><span>Completeness error</span><code>{explanation.completeness_error.toExponential(3)}</code></div>}
              <p>{explanation.scientific_note}</p>
            </section>
            <section className="trace-card">
              <strong>Feature effects</strong>
              {[...explanation.attributions].sort((a, b) => Math.abs(b.attribution) - Math.abs(a.attribution)).map((item) => (
                <div key={item.feature}>
                  <span>{item.feature}: {item.observed_value.toFixed(4)} → ref {item.reference_value.toFixed(4)}</span>
                  <code>{item.attribution >= 0 ? "+" : ""}{item.attribution.toFixed(6)}</code>
                </div>
              ))}
            </section>
            <section className="trace-card evidence-limitations">
              <strong>Assumptions / limits</strong>
              {explanation.assumptions.map((item) => <p key={item}>Assumption · {item}</p>)}
              {explanation.limitations.map((item) => <p key={item}>Limit · {item}</p>)}
            </section>
          </div>
        )}
      </section>

      {explanation && (
        <section className="evidence-section">
          <div className="feature-toolbar compact-toolbar">
            <div><span className="eyebrow">CHECK EXPLANATION</span><h3>Available technical checks</h3></div>
            <Button view="outlined" disabled={busy || project.read_only} onClick={check}>Run explanation checks</Button>
          </div>
          {explanationCheck ? (
            <div className="trace-card">
              <div className="evidence-check-header"><strong>Check result</strong><StatusBadge tone={statusTone(explanationCheck.status)}>{explanationCheck.status}</StatusBadge></div>
              {explanationCheck.checks.map((item) => (
                <div key={item.name}>
                  <span>{item.name} · {item.detail}</span>
                  <StatusBadge tone={statusTone(item.status)}>{item.status}</StatusBadge>
                </div>
              ))}
              <p>{explanationCheck.scientific_note}</p>
            </div>
          ) : <p className="property-description">Not checked yet. A generated explanation is not automatically validated.</p>}
        </section>
      )}
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">BEHAVIOR SPECS</span><h3>Revision-bound engineering checks</h3><p>Each execution binds to the persisted model artifact; PASS/FAIL is evidence, not a trust score.</p></div></div>
        {!run ? <EmptyState title="No trained model selected">Select a persisted training run before defining behavior evidence.</EmptyState> : <>
          <div className="contract-grid"><label className="field-label">Name<TextInput aria-label="Behavior spec name" value={behaviorName} onUpdate={setBehaviorName} /></label><label className="field-label">Type<select aria-label="Behavior spec type" value={behaviorKind} onChange={(event) => setBehaviorKind(event.target.value as BehaviorSpec["kind"])}><option value="output_range">Output range</option><option value="monotonic_pair">Monotonic pair</option><option value="invariance_pair">Invariance pair</option><option value="regression_case">Expert regression case</option></select></label>{behaviorKind === "monotonic_pair" && <label className="field-label">Direction<select aria-label="Monotonic direction" value={direction} onChange={(event) => setDirection(event.target.value as typeof direction)}><option value="nondecreasing">Nondecreasing</option><option value="nonincreasing">Nonincreasing</option></select></label>}{!(["monotonic_pair", "invariance_pair"] as string[]).includes(behaviorKind) && <><label className="field-label">Minimum<input aria-label="Behavior minimum" type="number" value={minimum} onChange={(event) => setMinimum(event.target.value)} /></label><label className="field-label">Maximum<input aria-label="Behavior maximum" type="number" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></label></>}</div>
          {(["monotonic_pair", "invariance_pair"] as string[]).includes(behaviorKind) && <><p className="field-help">Define both cases explicitly. RuFLEX does not infer a pairwise requirement from a single sample.</p><div className="evidence-sample-grid">{run.feature_columns.map((feature) => <label className="field-label" key={`comparison-${feature}`}>Comparison {feature}<input aria-label={`Behavior comparison ${feature}`} type="number" value={comparisonSample[feature] ?? ""} onChange={(event) => setComparisonSample((current) => ({ ...current, [feature]: event.target.value }))} /></label>)}</div></>}
          <Button view="action" disabled={busy || project.read_only} onClick={createAndRunBehavior}>{busy ? "Running…" : "Create and run BehaviorSpec"}</Button>
          {behaviorResult && <div className="trace-card" data-testid="behavior-result"><div className="evidence-check-header"><strong>{behaviorSpec?.name ?? "Persisted BehaviorSpec"}</strong><StatusBadge tone={behaviorResult.status === "PASS" ? "success" : "danger"}>{behaviorResult.status}</StatusBadge></div><p>{behaviorResult.detail}</p><small>{behaviorResult.run_id ? `Run ${behaviorResult.run_id.slice(0, 12)} · artifact ${behaviorResult.model_artifact_sha256?.slice(0, 12)}` : `FIS revision ${behaviorResult.fis_semantic_hash?.slice(0, 12)}`}</small></div>}
        </>}
      </section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">CONDITION MONITORING DEMO</span><h3>Telemetry decision support with review and scope safeguards</h3><p>Telemetry → frozen class/selective policy → scope → explanation check → AssuranceCase → VerificationBundle → ACCEPT / REVIEW / OUT-OF-SCOPE. This is not targeting or actuator control.</p></div><Button view="action" disabled={busy || project.read_only || !run || !selectivePolicy} onClick={runConditionDemo}>Run telemetry demonstration</Button></div>{!selectivePolicy && <p className="property-description">A validation-derived selective policy is required before this demonstration can make an ACCEPT/REVIEW decision.</p>}{demo && <div className="trace-card" data-testid="condition-monitoring-demo"><StatusBadge tone={demo.decision === "ACCEPT" ? "success" : demo.decision === "OUT_OF_SCOPE" ? "danger" : "warning"}>{demo.decision}</StatusBadge><p>Class {demo.predicted_class} · probability {demo.probability.toFixed(4)} · confidence {demo.confidence.toFixed(4)} · scope {demo.scope_disposition}</p><small className="mono">Explanation {demo.explanation_id?.slice(0, 12)} · check {demo.explanation_check_id?.slice(0, 12)} · AssuranceCase {demo.assurance_id?.slice(0, 12)} · VerificationBundle {demo.verification_bundle_sha256?.slice(0, 12)}</small><p>{demo.explanation_note}</p><small>{demo.safety_note}</small></div>}</section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">ASSURANCE CASE</span><h3>Independent evidence gates and qualified claims</h3><p>No universal trust score is produced.</p></div><Button view="action" disabled={busy || project.read_only} onClick={buildAssurance}>{busy ? "Building…" : "Build AssuranceCase"}</Button></div>{assurance && <div className="trace-card" data-testid="assurance-case"><p>{assurance.scientific_note}</p><div className="data-table-wrap"><table className="data-table"><thead><tr><th>gate</th><th>status</th><th>evidence / risk</th></tr></thead><tbody>{assurance.gates.map((gate) => <tr key={gate.key}><td>{gate.key.replaceAll("_", " ")}</td><td><StatusBadge tone={gate.status === "PASS" ? "success" : gate.status === "FAIL" ? "danger" : "warning"}>{gate.status}</StatusBadge></td><td>{gate.evidence.join(", ") || gate.risk || "—"}</td></tr>)}</tbody></table></div>{assurance.claims.length > 0 && <div className="assurance-claims"><strong>Claim graph</strong>{assurance.claims.map((claim) => <div className="property-description" key={claim.claim_id}><StatusBadge tone={claim.status === "SUPPORTED" ? "success" : claim.status === "UNSUPPORTED" ? "danger" : "warning"}>{claim.status}</StatusBadge><p>{claim.statement}</p><small>Evidence: {claim.evidence_ids.join(", ")}</small>{claim.limitations.map((limitation) => <small key={limitation}>Limitation: {limitation}</small>)}</div>)}</div>}{assurance.unresolved_risks.map((risk) => <p className="property-description" key={risk}>Unresolved risk · {risk}</p>)}</div>}</section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">VERIFICATION BUNDLE</span><h3>Inspection-first evidence export</h3><p>Exports declarative evidence and checksums; it excludes executable code, pickle/joblib, raw datasets, credentials, caches and node_modules.</p></div><Button view="outlined" disabled={busy || project.read_only || !assurance} onClick={exportBundle}>Export and validate bundle</Button></div>{bundle && <div className="trace-card" data-testid="verification-bundle"><p>{bundle.entry_count} inspection entries · SHA-256 {bundle.sha256}</p><small>{bundle.path}</small>{bundleValidation && <><div className="evidence-check-header"><strong>Portable validation</strong><StatusBadge tone={bundleValidation.status === "PASS" ? "success" : "danger"}>{bundleValidation.status}</StatusBadge></div><p>{bundleValidation.status === "PASS" ? `${bundleValidation.checked_entries} checksummed entries validated after export.` : bundleValidation.errors.join(" ")}</p>{bundleValidation.warnings.map((warning) => <p className="property-description" key={warning}>{warning}</p>)}</>}</div>}</section>
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">EXHAUSTIVE LAB</span><h3>Finite structure and declared discrete-grid evidence</h3><p>Exactness applies only to the finite tree structure or the explicitly declared FIS grid—not to arbitrary continuous models.</p></div></div>
        <div className="toolbar-actions">{run?.model_kind === "decision_tree" && <Button view="action" disabled={busy || project.read_only} onClick={() => runExhaustive("decision_tree_structure")}>Enumerate exact Decision Tree paths</Button>}{evaluation && <><label className="field-label">Grid points/input<input aria-label="Exhaustive grid points" type="number" min="2" max="9" value={gridPoints} onChange={(event) => setGridPoints(event.target.value)} /></label><Button view="outlined" disabled={busy || project.read_only} onClick={() => runExhaustive("fis_discrete_grid")}>Evaluate declared FIS grid</Button></>}</div>
        {exhaustive && <div className="trace-card" data-testid="exhaustive-result"><StatusBadge tone="info">{exhaustive.exactness_label}</StatusBadge><p>{exhaustive.scientific_note}</p><p>{exhaustive.state_count} enumerated states (preflight estimate {exhaustive.state_estimate}, limit {exhaustive.max_states}) · uncovered {exhaustive.uncovered_states.length} · dead rules on declared grid {exhaustive.dead_rules.length} · overlap states {exhaustive.conflict_states.length}</p>{exhaustive.kind === "decision_tree_structure" && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>leaf</th><th>constraints</th></tr></thead><tbody>{exhaustive.paths.slice(0, 20).map((item, index) => <tr key={index}><td>{String(item.leaf_id)}</td><td>{Array.isArray(item.constraints) ? item.constraints.join("; ") : "—"}</td></tr>)}</tbody></table></div>}{exhaustive.uncovered_states.length > 0 && <p className="property-description">Uncovered/undefined declared states are retained as evidence; they are not silently filled.</p>}</div>}
      </section>
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">CROSS-RUN EXPLANATION REPRODUCIBILITY</span><h3>Compare compatible frozen explanation evidence</h3><p>Prediction reproducibility and post-hoc explanation reproducibility are reported separately.</p></div></div>
        {persistedExplanations.length < 4 ? <EmptyState title="Need persisted explanation cases">Generate the same explanation method for the same declared cases across at least two compatible runs.</EmptyState> : <><div className="comparison-choice">{persistedExplanations.map((item) => <label key={item.explanation_id}><input type="checkbox" checked={selectedExplanationIds.includes(item.explanation_id)} onChange={(event) => setSelectedExplanationIds((current) => event.target.checked ? [...current, item.explanation_id] : current.filter((id) => id !== item.explanation_id))} />{item.run_id.slice(0, 8)} · {item.method} · case {item.sample_identity?.slice(-8)}</label>)}</div><Button view="action" disabled={busy || project.read_only || selectedExplanationIds.length < 4} onClick={compareReproducibility}>{busy ? "Comparing…" : "Compare explanation reproducibility"}</Button></>}
        {reproducibility && <div className="trace-card" data-testid="reproducibility-result"><p><StatusBadge tone="info">PREDICTION AGREEMENT</StatusBadge> class {(reproducibility.prediction_agreement.class_agreement * 100).toFixed(1)}% · mean |Δ| {reproducibility.prediction_agreement.mean_absolute_difference.toFixed(5)}</p><p><StatusBadge tone="warning">EXPLANATION AGREEMENT</StatusBadge> Spearman {reproducibility.explanation_agreement.mean_spearman?.toFixed(3) ?? "N/A"} · sign {(reproducibility.explanation_agreement.mean_sign_agreement * 100).toFixed(1)}% · top-k {(reproducibility.explanation_agreement.mean_top_k_overlap * 100).toFixed(1)}%</p><div className="data-table-wrap"><table className="data-table"><thead><tr><th>runs</th><th>prediction Δ</th><th>Spearman</th><th>sign</th><th>top-k</th></tr></thead><tbody>{reproducibility.pairwise.map((item) => <tr key={`${item.left_run_id}-${item.right_run_id}`}><td>{item.left_run_id.slice(0, 8)} / {item.right_run_id.slice(0, 8)}</td><td>{item.prediction_mean_absolute_difference.toFixed(5)}</td><td>{item.explanation_spearman?.toFixed(3) ?? "N/A"}</td><td>{(item.explanation_sign_agreement * 100).toFixed(1)}%</td><td>{(item.top_k_overlap * 100).toFixed(1)}%</td></tr>)}</tbody></table></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>feature</th><th>mean attribution</th><th>variability σ</th><th>sign agreement</th></tr></thead><tbody>{reproducibility.per_feature_variability.map((item) => <tr key={item.feature}><td>{item.feature}</td><td>{item.mean_attribution.toFixed(5)}</td><td>{item.standard_deviation.toFixed(5)}</td><td>{(item.sign_agreement * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>{reproducibility.warnings.map((warning) => <p className="property-description" key={warning}>Warning · {warning}</p>)}</div>}
      </section>
    </section>
  );
}
