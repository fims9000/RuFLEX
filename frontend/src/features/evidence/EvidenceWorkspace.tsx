import { useEffect, useMemo, useState } from "react";
import {
  DatasetState,
  ProductApiError,
  BehaviorSpec,
  BehaviorRevisionComparison,
  BehaviorSpecResult,
  ExplanationReproducibilityAnalysis,
  ExhaustiveLabResult,
  AssuranceCase,
  VerificationBundle,
  ConditionMonitoringDemo,
  GeneralizationResponse,
  ExplanationCheck,
  ExplanationContract,
  VerificationBundleValidation,
  FISEvaluation,
  PluginDescriptor,
  RunCapabilityNegotiation,
  RuntimeExplainerDescriptor,
  RuntimeValidatorDescriptor,
  ExecutionBackendDescriptor,
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
  explanationHydrationStatus = "available",
  explanationHydrationError = null,
  onRetryExplanation,
  explanationCheck,
  explanationCheckHydrationStatus = "available",
  explanationCheckHydrationError = null,
  onRetryExplanationCheck,
  behaviorSpec: restoredBehaviorSpec,
  lineageBehaviorComparison,
  behaviorResult: restoredBehaviorResult,
  reproducibility: restoredReproducibility,
  reproducibilityHydrationStatus = "available",
  reproducibilityHydrationError = null,
  onRetryReproducibility,
  exhaustive: restoredExhaustive,
  exhaustiveHydrationStatus = "available",
  exhaustiveHydrationError = null,
  onRetryExhaustive,
  assurance: restoredAssurance,
  verificationBundleRecord: restoredVerificationBundleRecord,
  selectivePolicy,
  generalization,
  generalizationHydrationStatus = "available",
  generalizationHydrationError = null,
  onRetryGeneralization,
  theme,
  onExplanation,
  onExplanationCheck,
  onBehaviorResult,
  behaviorSpecResultStatus = "available",
  behaviorSpecResultError = null,
  onRetryBehaviorSpecResult,
  onReproducibility,
  onExhaustive,
  onAssurance,
  assuranceHydrationStatus = "available",
  assuranceHydrationError = null,
  onRetryAssurance,
}: {
  project: ProjectSummary;
  dataset: DatasetState | null;
  run: TrainingRun | null;
  evaluation: FISEvaluation | null;
  previousEvaluation: FISEvaluation | null;
  treeEvidence: TreePathEvidence | null;
  explanation: ExplanationContract | null;
  explanationHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  explanationHydrationError?: string | null;
  onRetryExplanation?: () => void;
  explanationCheck: ExplanationCheck | null;
  explanationCheckHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  explanationCheckHydrationError?: string | null;
  onRetryExplanationCheck?: () => void;
  behaviorSpec: BehaviorSpec | null;
  lineageBehaviorComparison: BehaviorRevisionComparison | null;
  behaviorResult: BehaviorSpecResult | null;
  reproducibility: ExplanationReproducibilityAnalysis | null;
  reproducibilityHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  reproducibilityHydrationError?: string | null;
  onRetryReproducibility?: () => void;
  exhaustive: ExhaustiveLabResult | null;
  exhaustiveHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  exhaustiveHydrationError?: string | null;
  onRetryExhaustive?: () => void;
  assurance: AssuranceCase | null;
  verificationBundleRecord: VerificationBundle | null;
  selectivePolicy: import("../../api").SelectivePredictionPolicy | null;
  generalization: GeneralizationResponse | null;
  generalizationHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  generalizationHydrationError?: string | null;
  onRetryGeneralization?: () => void;
  theme: StudioTheme;
  onExplanation: (value: ExplanationContract | null) => void;
  onExplanationCheck: (value: ExplanationCheck | null) => void;
  onBehaviorResult: (value: BehaviorSpecResult | null) => void;
  behaviorSpecResultStatus?: "idle" | "loading" | "none" | "available" | "error";
  behaviorSpecResultError?: string | null;
  onRetryBehaviorSpecResult?: () => void;
  onReproducibility: (value: ExplanationReproducibilityAnalysis | null) => void;
  onExhaustive: (value: ExhaustiveLabResult | null) => void;
  onAssurance: (value: AssuranceCase | null) => void;
  assuranceHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  assuranceHydrationError?: string | null;
  onRetryAssurance?: () => void;
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
  const [method, setMethod] = useState("occlusion");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [behaviorKind, setBehaviorKind] = useState<BehaviorSpec["kind"]>("output_range");
  const [behaviorName, setBehaviorName] = useState("Output remains in declared range");
  const [maximumDelta, setMaximumDelta] = useState("0.1");
  const [minimum, setMinimum] = useState("0");
  const [maximum, setMaximum] = useState("1");
  const [direction, setDirection] = useState<"nondecreasing" | "nonincreasing">("nondecreasing");
  const [behaviorSpec, setBehaviorSpec] = useState<BehaviorSpec | null>(restoredBehaviorSpec);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorSpecResult | null>(restoredBehaviorResult);
  const [behaviorExecutionRecoveryError, setBehaviorExecutionRecoveryError] = useState<string | null>(null);
  const [behaviorResults, setBehaviorResults] = useState<BehaviorSpecResult[]>([]);
  const [behaviorResultsHydrationStatus, setBehaviorResultsHydrationStatus] = useState<"loading" | "available" | "error">("loading");
  const [behaviorResultsHydrationError, setBehaviorResultsHydrationError] = useState<string | null>(null);
  const [behaviorResultsHydrationReload, setBehaviorResultsHydrationReload] = useState(0);
  const [behaviorComparison, setBehaviorComparison] = useState<BehaviorRevisionComparison | null>(null);
  const [behaviorComparisonHydrationStatus, setBehaviorComparisonHydrationStatus] = useState<"loading" | "none" | "available" | "error">("loading");
  const [behaviorComparisonHydrationError, setBehaviorComparisonHydrationError] = useState<string | null>(null);
  const [behaviorComparisonHydrationReload, setBehaviorComparisonHydrationReload] = useState(0);
  const [baselineBehaviorResultId, setBaselineBehaviorResultId] = useState("");
  const [candidateBehaviorResultId, setCandidateBehaviorResultId] = useState("");
  const [reproducibility, setReproducibility] = useState<ExplanationReproducibilityAnalysis | null>(restoredReproducibility);
  const [reproducibilityRecoveryIds, setReproducibilityRecoveryIds] = useState<string[] | null>(null);
  const [reproducibilityRecoveryError, setReproducibilityRecoveryError] = useState<string | null>(null);
  const [reproducibilityRecoveryNotFound, setReproducibilityRecoveryNotFound] = useState(false);
  const [persistedExplanations, setPersistedExplanations] = useState<ExplanationContract[]>([]);
  const [persistedExplanationsHydrationStatus, setPersistedExplanationsHydrationStatus] = useState<"loading" | "available" | "error">("loading");
  const [persistedExplanationsHydrationError, setPersistedExplanationsHydrationError] = useState<string | null>(null);
  const [persistedExplanationsHydrationReload, setPersistedExplanationsHydrationReload] = useState(0);
  const [selectedExplanationIds, setSelectedExplanationIds] = useState<string[]>([]);
  const [exhaustive, setExhaustive] = useState<ExhaustiveLabResult | null>(restoredExhaustive);
  const [gridPoints, setGridPoints] = useState("3");
  const [assurance, setAssurance] = useState<AssuranceCase | null>(restoredAssurance);
  const [evidenceOperationJob, setEvidenceOperationJob] = useState<ProductJob | null>(null);
  const [evidenceOperationPollError, setEvidenceOperationPollError] = useState<string | null>(null);
  const [bundle, setBundle] = useState<{ path: string; sha256: string; entry_count: number } | null>(null);
  const [bundleValidation, setBundleValidation] = useState<VerificationBundleValidation | null>(null);
  const [verificationBundleRecord, setVerificationBundleRecord] = useState<VerificationBundle | null>(restoredVerificationBundleRecord);
  const [demo, setDemo] = useState<ConditionMonitoringDemo | null>(null);
  const [demoHydrationStatus, setDemoHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [demoHydrationError, setDemoHydrationError] = useState<string | null>(null);
  const [demoHydrationReload, setDemoHydrationReload] = useState(0);
  const [explanationJob, setExplanationJob] = useState<ProductJob | null>(null);
  const [explanationJobHydrationStatus, setExplanationJobHydrationStatus] = useState<"loading" | "none" | "available" | "error">("loading");
  const [explanationJobHydrationError, setExplanationJobHydrationError] = useState<string | null>(null);
  const [explanationJobHydrationReload, setExplanationJobHydrationReload] = useState(0);
  const [explanationJobPollError, setExplanationJobPollError] = useState<string | null>(null);
  const [capabilityNegotiation, setCapabilityNegotiation] = useState<RunCapabilityNegotiation | null>(null);
  const [capabilityHydrationStatus, setCapabilityHydrationStatus] = useState<"loading" | "available" | "error">("loading");
  const [capabilityHydrationError, setCapabilityHydrationError] = useState<string | null>(null);
  const [capabilityHydrationReload, setCapabilityHydrationReload] = useState(0);
  const [validatorPlugins, setValidatorPlugins] = useState<PluginDescriptor[]>([]);
  const [runtimeExplainers, setRuntimeExplainers] = useState<RuntimeExplainerDescriptor[]>([]);
  const [runtimeValidators, setRuntimeValidators] = useState<RuntimeValidatorDescriptor[]>([]);
  const [validatorKey, setValidatorKey] = useState("native_explanation_validator");
  const [executionBackends, setExecutionBackends] = useState<ExecutionBackendDescriptor[]>([]);
  const [executionBackendKey, setExecutionBackendKey] = useState("local_executor");
  const [runtimeCatalogHydrationStatus, setRuntimeCatalogHydrationStatus] = useState<"loading" | "available" | "error">("loading");
  const [runtimeCatalogHydrationError, setRuntimeCatalogHydrationError] = useState<string | null>(null);
  const [runtimeCatalogHydrationReload, setRuntimeCatalogHydrationReload] = useState(0);

  useEffect(() => { setSample(initialSample); setComparisonSample(initialSample); }, [initialSample]);
  useEffect(() => setBehaviorResult(restoredBehaviorResult), [restoredBehaviorResult?.result_id]);
  useEffect(() => setBehaviorSpec(restoredBehaviorSpec), [restoredBehaviorSpec?.spec_id]);
  useEffect(() => {
    let active = true;
    setBehaviorResultsHydrationStatus("loading");
    setBehaviorResultsHydrationError(null);
    studioApi.listBehaviorResults(project.session_id).then((results) => {
      if (!active) return;
      setBehaviorResults(results);
      setBaselineBehaviorResultId(results[1]?.result_id || "");
      setCandidateBehaviorResultId(results[0]?.result_id || "");
      setBehaviorResultsHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setBehaviorResultsHydrationError(reason instanceof Error ? reason.message : "Saved BehaviorSpec results could not be verified.");
      setBehaviorResultsHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project.session_id, behaviorResultsHydrationReload]);
  useEffect(() => {
    let active = true;
    setBehaviorComparisonHydrationStatus("loading");
    setBehaviorComparisonHydrationError(null);
    studioApi.listBehaviorRevisionComparisons(project.session_id).then((comparisons) => {
      if (!active) return;
      const comparison = comparisons[0] ?? null;
      setBehaviorComparison(comparison);
      setBehaviorComparisonHydrationStatus(comparison ? "available" : "none");
    }).catch((reason: unknown) => {
      if (!active) return;
      setBehaviorComparisonHydrationError(reason instanceof Error ? reason.message : "Saved behavior comparison could not be verified.");
      setBehaviorComparisonHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project.session_id, behaviorComparisonHydrationReload]);
  useEffect(() => setReproducibility(restoredReproducibility), [restoredReproducibility?.analysis_id]);
  useEffect(() => setExhaustive(restoredExhaustive), [restoredExhaustive?.result_id]);
  useEffect(() => setAssurance(restoredAssurance), [restoredAssurance?.assurance_id]);
  useEffect(() => setVerificationBundleRecord(restoredVerificationBundleRecord), [restoredVerificationBundleRecord?.bundle_id]);
  useEffect(() => {
    let active = true;
    setDemo(null);
    setDemoHydrationError(null);
    setDemoHydrationStatus("loading");
    studioApi.getLatestConditionMonitoringDemo(project.session_id).then((value) => {
      if (!active) return;
      setDemo(value);
      setDemoHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setDemo(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setDemoHydrationStatus("none");
        return;
      }
      setDemoHydrationError(reason instanceof Error ? reason.message : "Saved condition-monitoring evidence could not be verified.");
      setDemoHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project.session_id, demoHydrationReload]);
  useEffect(() => {
    let active = true;
    setExplanationJobHydrationStatus("loading");
    setExplanationJobHydrationError(null);
    studioApi.listPosthocExplanationJobs(project.session_id).then((jobs) => {
      if (!active) return;
      const job = jobs[0] ?? null;
      setExplanationJob(job);
      setExplanationJobHydrationStatus(job ? "available" : "none");
    }).catch((reason: unknown) => {
      if (!active) return;
      setExplanationJobHydrationError(reason instanceof Error ? reason.message : "Saved explanation job could not be verified.");
      setExplanationJobHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project.session_id, explanationJobHydrationReload]);
  useEffect(() => {
    let active = true;
    setPersistedExplanationsHydrationStatus("loading");
    setPersistedExplanationsHydrationError(null);
    studioApi.listExplanations(project.session_id).then((items) => {
      if (!active) return;
      setPersistedExplanations(items);
      setPersistedExplanationsHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setPersistedExplanationsHydrationError(reason instanceof Error ? reason.message : "Persisted explanations could not be verified.");
      setPersistedExplanationsHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project.session_id, persistedExplanationsHydrationReload]);
  useEffect(() => {
    let active = true;
    setRuntimeCatalogHydrationStatus("loading");
    setRuntimeCatalogHydrationError(null);
    Promise.all([
      studioApi.getPluginCatalog(), studioApi.getRuntimeExplainers(),
      studioApi.getRuntimeValidators(), studioApi.getRuntimeBackends(),
    ]).then(([plugins, explainers, validators, backends]) => {
      if (!active) return;
      setValidatorPlugins(plugins);
      setRuntimeExplainers(explainers);
      setRuntimeValidators(validators);
      if (!validators.some((validator) => validator.identity.key === validatorKey)) setValidatorKey(validators[0]?.identity.key ?? "native_explanation_validator");
      setExecutionBackends(backends);
      if (!backends.some((backend) => backend.identity.key === executionBackendKey)) setExecutionBackendKey(backends[0]?.identity.key ?? "local_executor");
      setRuntimeCatalogHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setRuntimeCatalogHydrationError(reason instanceof Error ? reason.message : "Runtime explainer, validator and execution-backend catalogs could not be verified.");
      setRuntimeCatalogHydrationStatus("error");
    });
    return () => { active = false; };
  }, [runtimeCatalogHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!run) {
      setCapabilityNegotiation(null);
      setCapabilityHydrationStatus("error");
      setCapabilityHydrationError("Select a persisted TrainingRun before resolving explanation capabilities.");
      return () => { active = false; };
    }
    setCapabilityNegotiation(null);
    setCapabilityHydrationStatus("loading");
    setCapabilityHydrationError(null);
    studioApi.getTrainingRunCapabilities(project.session_id, run.run_id)
      .then((value) => {
        if (!active) return;
        setCapabilityNegotiation(value);
        setCapabilityHydrationStatus("available");
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setCapabilityHydrationError(reason instanceof Error ? reason.message : "The selected run's explainer capabilities could not be verified.");
        setCapabilityHydrationStatus("error");
      });
    return () => { active = false; };
  }, [project.session_id, run?.run_id, capabilityHydrationReload]);
  const availableMethods = useMemo(() => {
    return capabilityNegotiation?.decisions
      .filter((decision) => decision.status === "AVAILABLE" && decision.capability !== "exact_tree_path")
      .map((decision) => decision.capability) ?? [];
  }, [capabilityNegotiation]);
  const selectableMethods = useMemo(() => {
    const external = runtimeExplainers
      .filter((explainer) => explainer.identity.provider !== "ruflex.builtin" && !!run && explainer.supported_tasks.includes(run.task))
      .map((explainer) => explainer.identity.key);
    return [...new Set([...availableMethods, ...external])];
  }, [availableMethods, run?.task, runtimeExplainers]);
  useEffect(() => {
    if (!run || selectableMethods.length === 0) return;
    if (!selectableMethods.includes(method)) setMethod(selectableMethods[0]);
  }, [run?.run_id, selectableMethods, method]);

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
    if (demoHydrationStatus !== "none" && demoHydrationStatus !== "available") { setError("Resolve the saved condition-monitoring evidence before starting another run."); return; }
    if (generalizationHydrationStatus === "loading" || generalizationHydrationStatus === "error" || generalizationHydrationStatus === "idle") {
      setError("Resolve the saved GeneralizationContract state before running the scope-aware condition-monitoring demo.");
      return;
    }
    setBusy(true); setError(null);
    try { setDemo(await studioApi.runConditionMonitoringDemo(project.session_id, numericSample(), selectivePolicy.policy_id, generalization?.contract.contract_id ?? null)); setDemoHydrationStatus("available"); setDemoHydrationError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function generate() {
    if (!run) return;
    setBusy(true);
    setError(null);
    let job: ProductJob | null = null;
    try {
      job = await studioApi.startPosthocExplanationJob(project.session_id, run.run_id, numericSample(), method, executionBackendKey);
      setExplanationJob(job);
      setExplanationJobHydrationStatus("available");
      setExplanationJobHydrationError(null);
      setExplanationJobPollError(null);
      await completeExplanationJob(job);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function completeExplanationJob(initialJob: ProductJob) {
    let job = initialJob;
    for (let attempt = 0; attempt < 120 && ["queued", "running"].includes(job.status); attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
      try {
        job = await studioApi.getPosthocExplanationJob(project.session_id, job.job_id);
      } catch (reason) {
        setExplanationJobPollError(reason instanceof Error ? reason.message : "Could not read the persisted explanation job status.");
        throw reason;
      }
      setExplanationJob(job);
    }
    if (["queued", "running"].includes(job.status)) {
      setExplanationJobPollError("This job is still active. Resume this exact saved job instead of starting another one.");
      return;
    }
    if (job.status !== "succeeded") throw new Error(job.error ?? job.message ?? "Explanation evidence job did not complete successfully.");
    if (job.kind === "explanation_generation" && job.output.explanation_id) {
      try {
        onExplanation(await studioApi.getExplanation(project.session_id, job.output.explanation_id));
      } catch (reason) {
        setExplanationJobPollError(reason instanceof Error ? reason.message : "The saved explanation output could not be loaded.");
        throw reason;
      }
      setExplanationJobPollError(null);
      setPersistedExplanationsHydrationReload((current) => current + 1);
      onExplanationCheck(null);
      return;
    }
    if (job.kind === "explanation_check" && job.output.check_id) {
      try {
        onExplanationCheck(await studioApi.getExplanationCheck(project.session_id, job.output.check_id));
      } catch (reason) {
        setExplanationJobPollError(reason instanceof Error ? reason.message : "The saved ExplanationCheck output could not be loaded.");
        throw reason;
      }
      setExplanationJobPollError(null);
      return;
    }
    setExplanationJobPollError("The completed job has no resolvable output identity; do not create another job from this uncertain result.");
    throw new Error(`Saved job ${job.job_id} succeeded without the expected explanation evidence identity.`);
  }

  async function resumeExplanationJob() {
    if (!explanationJob || (!["queued", "running"].includes(explanationJob.status) && !explanationJobPollError)) return;
    setBusy(true);
    setError(null);
    setExplanationJobPollError(null);
    try {
      await completeExplanationJob(explanationJob);
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
    let job: ProductJob | null = null;
    try {
      job = await studioApi.startExplanationCheckJob(project.session_id, explanation.explanation_id, validatorKey, executionBackendKey);
      setExplanationJob(job);
      setExplanationJobHydrationStatus("available");
      setExplanationJobHydrationError(null);
      setExplanationJobPollError(null);
      await completeExplanationJob(job);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }
  async function cancelQueuedJob() {
    if (!explanationJob || explanationJob.status !== "queued") return;
    setError(null);
    try { setExplanationJob(await studioApi.cancelEvidenceJob(project.session_id, explanationJob.job_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function createAndRunBehavior() {
    if (!run) return;
    setBusy(true); setError(null);
    let createdSpec: BehaviorSpec | null = null;
    try {
      const numeric = numericSample();
      const pairKinds = ["monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order", "batch_regression_suite"];
      const rangeKinds = ["output_range", "regression_case", "domain_constraint", "forbidden_region", "batch_regression_suite"];
      const pair = pairKinds.includes(behaviorKind) ? numericComparisonSample() : null;
      const created = await studioApi.createBehaviorSpec(project.session_id, {
        run_id: run.run_id, name: behaviorName, kind: behaviorKind, sample: numeric, comparison_sample: pair,
        minimum: rangeKinds.includes(behaviorKind) ? Number(minimum) : null,
        maximum: rangeKinds.includes(behaviorKind) ? Number(maximum) : null,
        expected_direction: ["monotonic_pair", "required_order"].includes(behaviorKind) ? direction : null,
        maximum_delta: behaviorKind === "bounded_perturbation" ? Number(maximumDelta) : null,
        cases: behaviorKind === "batch_regression_suite" ? [{ name: "primary", sample: numeric, minimum: Number(minimum), maximum: Number(maximum) }, { name: "comparison", sample: pair ?? numeric, minimum: Number(minimum), maximum: Number(maximum) }] : [],
        tolerance: 1e-9, rationale: "Persisted engineering behavior requirement.",
      });
      createdSpec = created;
      setBehaviorSpec(created);
      setBehaviorExecutionRecoveryError(null);
      const result = await studioApi.runBehaviorSpec(project.session_id, created.spec_id);
      setBehaviorResult(result); onBehaviorResult(result); setBehaviorResultsHydrationReload((current) => current + 1);
    } catch (reason) {
      if (createdSpec) setBehaviorExecutionRecoveryError(reason instanceof Error ? reason.message : "The saved BehaviorSpec result could not be confirmed.");
      setError(reason instanceof Error ? reason.message : String(reason));
    }
    finally { setBusy(false); }
  }

  async function resumeBehaviorSpecExecution() {
    if (!behaviorSpec) return;
    setBusy(true); setError(null);
    try {
      const results = await studioApi.listBehaviorResults(project.session_id);
      const existing = results.find((item) => item.spec_id === behaviorSpec.spec_id);
      const result = existing ?? await studioApi.runBehaviorSpec(project.session_id, behaviorSpec.spec_id);
      setBehaviorResult(result);
      onBehaviorResult(result);
      setBehaviorExecutionRecoveryError(null);
      setBehaviorResultsHydrationReload((current) => current + 1);
    } catch (reason) {
      setBehaviorExecutionRecoveryError(reason instanceof Error ? reason.message : "Could not recover the result for this saved BehaviorSpec.");
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function compareBehaviorRevisions() {
    if (!baselineBehaviorResultId || !candidateBehaviorResultId) return;
    setBusy(true); setError(null);
    try {
      setBehaviorComparison(await studioApi.compareBehaviorResults(project.session_id, baselineBehaviorResultId, candidateBehaviorResultId));
      setBehaviorComparisonHydrationStatus("available");
      setBehaviorComparisonHydrationError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not compare BehaviorSpec revisions"); }
    finally { setBusy(false); }
  }

  async function compareReproducibility() {
    setBusy(true); setError(null);
    const explanationIds = [...selectedExplanationIds];
    try {
      await submitReproducibility(explanationIds);
    } catch (reason) {
      setReproducibilityRecoveryIds(explanationIds);
      setReproducibilityRecoveryError(reason instanceof Error ? reason.message : "The saved reproducibility analysis could not be confirmed.");
      setReproducibilityRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    }
    finally { setBusy(false); }
  }

  async function submitReproducibility(explanationIds: string[]) {
    const result = await studioApi.createExplanationReproducibility(project.session_id, explanationIds);
    setReproducibility(result); onReproducibility(result);
    setReproducibilityRecoveryIds(null);
    setReproducibilityRecoveryError(null);
    setReproducibilityRecoveryNotFound(false);
  }

  async function recoverReproducibility() {
    if (!reproducibilityRecoveryIds) return;
    setBusy(true); setError(null);
    try {
      let result: ExplanationReproducibilityAnalysis;
      try {
        result = await studioApi.getLatestExplanationReproducibility(project.session_id);
      } catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) {
          setReproducibilityRecoveryNotFound(true);
          setReproducibilityRecoveryError("No persisted comparison is visible yet. Retry lookup later, or explicitly start a new comparison if the original request did not finish.");
          return;
        }
        throw reason;
      }
      const expected = [...reproducibilityRecoveryIds].sort();
      if ([...result.explanation_ids].sort().join("\n") !== expected.join("\n")) {
        throw new Error("The latest saved analysis belongs to a different explanation set; no replacement was created.");
      }
      setReproducibility(result); onReproducibility(result);
      setReproducibilityRecoveryIds(null);
      setReproducibilityRecoveryError(null);
      setReproducibilityRecoveryNotFound(false);
    } catch (reason) {
      setReproducibilityRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact saved reproducibility analysis.");
      setReproducibilityRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function explicitlyRestartReproducibility() {
    if (!reproducibilityRecoveryIds || !reproducibilityRecoveryNotFound) return;
    setBusy(true); setError(null);
    try {
      await submitReproducibility(reproducibilityRecoveryIds);
    } catch (reason) {
      setReproducibilityRecoveryError(reason instanceof Error ? reason.message : "The replacement comparison could not be confirmed.");
      setReproducibilityRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  async function runExhaustive(kind: ExhaustiveLabResult["kind"]) {
    setBusy(true); setError(null);
    try { const result=await studioApi.runExhaustiveLab(project.session_id, kind, kind === "decision_tree_structure" ? run?.run_id ?? null : null, Number(gridPoints)); setExhaustive(result); onExhaustive(result); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function waitForEvidenceOperation(job: ProductJob) {
    setEvidenceOperationJob(job);
    for (let attempt = 0; attempt < 120 && ["queued", "running"].includes(job.status); attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
      try {
        job = await studioApi.getPosthocExplanationJob(project.session_id, job.job_id);
      } catch (reason) {
        setEvidenceOperationPollError(reason instanceof Error ? reason.message : "Could not read the persisted evidence operation status.");
        throw reason;
      }
      setEvidenceOperationJob(job);
    }
    if (["queued", "running"].includes(job.status)) {
      setEvidenceOperationPollError("This evidence operation is still active. Resume this exact saved job instead of starting another one.");
      return job;
    }
    if (job.status !== "succeeded") throw new Error(job.error ?? job.message ?? "Evidence operation did not complete successfully.");
    setEvidenceOperationPollError(null);
    return job;
  }
  async function applyEvidenceOperationResult(job: ProductJob) {
    if (job.kind === "assurance_case") {
      if (!job.output.assurance_id) throw new Error("Assurance job did not return its persisted AssuranceCase identity.");
      const result = await studioApi.getAssuranceCase(project.session_id, job.output.assurance_id);
      setAssurance(result);
      onAssurance(result);
      return;
    }
    if (job.kind === "verification_bundle_export") {
      const exported = { path: job.output.path, sha256: job.output.sha256, entry_count: Number(job.output.entry_count) };
      if (!exported.path || !exported.sha256 || !Number.isFinite(exported.entry_count)) throw new Error("VerificationBundle job did not persist a complete export receipt.");
      setBundle(exported);
      setBundleValidation(await studioApi.validateVerificationBundle(exported.path));
      return;
    }
    throw new Error(`Unsupported persisted evidence operation kind: ${job.kind}`);
  }
  async function resumeEvidenceOperation() {
    if (!evidenceOperationJob || !["queued", "running"].includes(evidenceOperationJob.status)) return;
    setBusy(true); setError(null); setEvidenceOperationPollError(null);
    try {
      const job = await waitForEvidenceOperation(evidenceOperationJob);
      if (job.status === "succeeded") await applyEvidenceOperationResult(job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function buildAssurance() {
    setBusy(true); setError(null); setEvidenceOperationPollError(null);
    try {
      const job = await waitForEvidenceOperation(await studioApi.startAssuranceCaseJob(project.session_id, executionBackendKey));
      if (job.status === "succeeded") await applyEvidenceOperationResult(job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function exportBundle() {
    setBusy(true); setError(null); setEvidenceOperationPollError(null);
    try {
      const job = await waitForEvidenceOperation(await studioApi.startVerificationBundleJob(project.session_id, executionBackendKey));
      if (job.status === "succeeded") await applyEvidenceOperationResult(job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  const hasExact = Boolean(evaluation || treeEvidence);
  const evidenceOperationPending = Boolean(evidenceOperationJob && ["queued", "running"].includes(evidenceOperationJob.status));

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
        {explanationHydrationStatus === "loading" && <p role="status">Loading saved explanation…</p>}
        {explanationHydrationStatus === "none" && <p className="property-description" data-testid="explanation-empty">No saved explanation is available for this project.</p>}
        {explanationHydrationStatus === "error" && <div className="error" role="alert" data-testid="explanation-hydration-error"><strong>Saved explanation could not be verified.</strong><p>{explanationHydrationError}</p>{onRetryExplanation && <Button view="outlined" onClick={onRetryExplanation}>Retry saved explanation</Button>}</div>}
        {!run ? (
          <EmptyState title="No trained model selected">Train or reopen a catalog model to generate a local attribution.</EmptyState>
        ) : (
          <>
            <label className="field-label evidence-method-select">Method
              <select aria-label="Explanation method" value={method} disabled={capabilityHydrationStatus !== "available"} onChange={(event) => setMethod(event.target.value)}>
                {selectableMethods.map((candidate) => <option value={candidate} key={candidate}>{candidate === "occlusion" ? "Occlusion" : candidate === "shap" ? "SHAP · permutation" : candidate === "tree_shap" ? "TreeSHAP" : candidate === "integrated_gradients" ? "Integrated Gradients" : candidate === "gradient_shap" ? "GradientSHAP" : `${candidate} · runtime explainer`}</option>)}
              </select>
            </label>
            <label className="field-label evidence-method-select">Execution backend<select aria-label="Evidence execution backend" value={executionBackendKey} disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !executionBackends.length} onChange={(event) => setExecutionBackendKey(event.target.value)}>{executionBackends.map((backend) => <option key={backend.identity.key} value={backend.identity.key}>{backend.identity.key} · {backend.identity.provider}</option>)}</select></label>
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
              <Button view="action" disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !executionBackends.length || capabilityHydrationStatus !== "available" || selectableMethods.length === 0 || explanationJobHydrationStatus === "loading" || explanationJobHydrationStatus === "error" || !!explanationJobPollError || !!explanationJob && ["queued", "running"].includes(explanationJob.status)} onClick={generate} data-ruflex-action="explanation.generate">{busy ? "Generating…" : "Generate explanation"}</Button>
              <span className="property-description">{run.model_kind} · run {run.run_id.slice(0, 8)}</span>
            </div>
            {capabilityNegotiation && <div className="trace-card" data-testid="run-capability-negotiation"><strong>Run capability contract</strong><div className="property-list">{capabilityNegotiation.decisions.map((decision) => <div key={decision.capability}><span>{decision.capability.replaceAll("_", " ")}</span><span><StatusBadge tone={decision.status === "AVAILABLE" ? "success" : "info"}>{decision.status}</StatusBadge> {decision.detail}</span></div>)}</div></div>}
            {capabilityHydrationStatus === "loading" && <p role="status" data-testid="run-capability-loading">Checking explainer support for this exact run…</p>}
            {capabilityHydrationStatus === "error" && <div className="error" role="alert" data-testid="run-capability-error"><strong>Explainer support for this run could not be verified; generation is paused.</strong><p>{capabilityHydrationError}</p><Button view="outlined" onClick={() => setCapabilityHydrationReload((current) => current + 1)}>Retry run capabilities</Button></div>}
            {runtimeCatalogHydrationStatus === "loading" && <p role="status" data-testid="runtime-catalog-loading">Loading runtime explainer, validator and execution-backend catalogs…</p>}
            {runtimeCatalogHydrationStatus === "error" && <div className="error" role="alert" data-testid="runtime-catalog-error"><strong>Runtime catalogs could not be verified; evidence jobs are paused.</strong><p>{runtimeCatalogHydrationError}</p><Button view="outlined" onClick={() => setRuntimeCatalogHydrationReload((current) => current + 1)}>Retry runtime catalogs</Button></div>}
            {runtimeCatalogHydrationStatus === "available" && !executionBackends.length && <p className="property-description" data-testid="runtime-backends-empty">No execution backend is available; evidence jobs cannot be started.</p>}
            {explanationJobHydrationStatus === "loading" && <p role="status" data-testid="explanation-job-loading">Loading saved explanation job…</p>}
            {explanationJobHydrationStatus === "none" && <p className="property-description" data-testid="explanation-job-empty">No saved explanation job is available.</p>}
            {explanationJobHydrationStatus === "error" && <div className="error" role="alert" data-testid="explanation-job-hydration-error"><strong>Saved explanation job could not be verified; starting another operation is paused.</strong><p>{explanationJobHydrationError}</p><Button view="outlined" onClick={() => setExplanationJobHydrationReload((current) => current + 1)}>Retry saved explanation job</Button></div>}
            {explanationJob && <div className="property-description" data-testid="explanation-job"><StatusBadge tone={explanationJob.status === "succeeded" ? "success" : explanationJob.status === "failed" ? "danger" : "warning"}>{explanationJob.status.toUpperCase()}</StatusBadge> {explanationJob.execution_backend_key ?? "frozen execution backend"} · {explanationJob.message ?? "Persisted operation"} · job {explanationJob.job_id.slice(0, 12)}{explanationJob.error && ` · ${explanationJob.error}`}{explanationJob.status === "queued" && <Button view="flat" size="s" onClick={cancelQueuedJob} data-ruflex-action="explanation.cancel">Cancel queued job</Button>}</div>}
            {explanationJob && (["queued", "running"].includes(explanationJob.status) || !!explanationJobPollError) && <div className={explanationJobPollError ? "error" : "property-description"} role={explanationJobPollError ? "alert" : "status"} data-testid="explanation-job-resume">{explanationJobPollError ? <><strong>{explanationJob.status === "succeeded" ? "Saved job output needs recovery." : "Saved job status needs recovery."}</strong><p>{explanationJobPollError}</p></> : <span>This saved job is still active. New explanation/check jobs are paused to prevent duplicate work.</span>}<Button view="outlined" disabled={busy} onClick={resumeExplanationJob}>{explanationJob.status === "succeeded" ? "Recover saved job result" : "Resume saved job"}</Button></div>}
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
            <label className="field-label">Validator<select aria-label="Explanation validator" value={validatorKey} disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !runtimeValidators.length} onChange={(event) => setValidatorKey(event.target.value)}>{runtimeValidators.map((validator) => <option key={validator.identity.key} value={validator.identity.key}>{validator.identity.key} · {validator.identity.provider}</option>)}</select></label>
            <Button view="outlined" disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !runtimeValidators.length || !executionBackends.length || explanationJobHydrationStatus === "loading" || explanationJobHydrationStatus === "error" || !!explanationJobPollError || !!explanationJob && ["queued", "running"].includes(explanationJob.status)} onClick={check} data-ruflex-action="explanation.check">Run explanation checks</Button>
          </div>
          {explanationCheck && explanationCheck.explanation_id !== explanation.explanation_id ? <div className="error" role="alert" data-testid="explanation-check-mismatch"><strong>Saved check belongs to a different explanation.</strong><p>The persisted ExplanationCheck is not displayed as validation of the currently selected explanation.</p></div> : explanationCheck ? (
            <div className="trace-card">
              <div className="evidence-check-header"><strong>Check result</strong><StatusBadge tone={statusTone(explanationCheck.status)}>{explanationCheck.status}</StatusBadge></div>
              {validatorPlugins.filter((plugin) => explanationCheck.checks.some((item) => item.validator_key === plugin.key)).map((plugin) => <p className="property-description" data-testid="validator-plugin" key={plugin.key}>Validator · {plugin.key} v{plugin.version} · {Object.entries(plugin.capabilities).filter(([, available]) => available).map(([key]) => key.replaceAll("_", " ")).join(", ")}</p>)}
              {explanationCheck.checks.map((item) => (
                <div key={item.name}>
                  <span><strong>{item.category.replaceAll("_", " ")}</strong> · {item.name} · {item.detail}</span>
                  <StatusBadge tone={statusTone(item.status)}>{item.status}</StatusBadge>
                </div>
              ))}
              <p>{explanationCheck.scientific_note}</p>
            </div>
          ) : explanationCheckHydrationStatus === "error" ? <div className="error" role="alert" data-testid="explanation-check-hydration-error"><strong>Saved explanation check could not be verified.</strong><p>{explanationCheckHydrationError}</p>{onRetryExplanationCheck && <Button view="outlined" onClick={onRetryExplanationCheck}>Retry explanation check</Button>}</div> : explanationCheckHydrationStatus === "loading" ? <p role="status">Loading saved explanation check…</p> : <p className="property-description">Not checked yet. A generated explanation is not automatically validated.</p>}
        </section>
      )}
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">BEHAVIOR SPECS</span><h3>Revision-bound engineering checks</h3><p>Each execution binds to the persisted model artifact; PASS/FAIL is evidence, not a trust score.</p></div></div>
        {behaviorSpecResultStatus === "loading" && <p role="status">Loading saved BehaviorSpec result and its exact specification…</p>}
        {behaviorSpecResultStatus === "none" && <p className="property-description" data-testid="behavior-result-empty">No saved BehaviorSpec result is available for this project.</p>}
        {behaviorSpecResultStatus === "error" && <div className="error" role="alert"><strong>Saved BehaviorSpec evidence could not be verified.</strong><p>{behaviorSpecResultError}</p>{onRetryBehaviorSpecResult && <Button view="outlined" onClick={onRetryBehaviorSpecResult}>Retry saved BehaviorSpec</Button>}</div>}
        {!run ? <EmptyState title="No trained model selected">Select a persisted training run before defining behavior evidence.</EmptyState> : <>
          <div className="contract-grid"><label className="field-label">Name<TextInput aria-label="Behavior spec name" value={behaviorName} onUpdate={setBehaviorName} /></label><label className="field-label">Type<select aria-label="Behavior spec type" value={behaviorKind} onChange={(event) => setBehaviorKind(event.target.value as BehaviorSpec["kind"])}><option value="output_range">Output range</option><option value="monotonic_pair">Monotonic pair</option><option value="invariance_pair">Invariance pair</option><option value="symmetry_pair">Symmetry pair</option><option value="bounded_perturbation">Bounded perturbation</option><option value="categorical_invariance">Categorical invariance</option><option value="forbidden_region">Forbidden output region</option><option value="required_order">Required order</option><option value="domain_constraint">Domain constraint</option><option value="regression_case">Expert regression case</option><option value="batch_regression_suite">Two-case regression suite</option></select></label>{(["monotonic_pair", "required_order"] as string[]).includes(behaviorKind) && <label className="field-label">Direction<select aria-label="Monotonic direction" value={direction} onChange={(event) => setDirection(event.target.value as typeof direction)}><option value="nondecreasing">Nondecreasing</option><option value="nonincreasing">Nonincreasing</option></select></label>}{behaviorKind === "bounded_perturbation" && <label className="field-label">Maximum delta<input aria-label="Behavior maximum delta" type="number" value={maximumDelta} onChange={(event) => setMaximumDelta(event.target.value)} /></label>}{!(["monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order"] as string[]).includes(behaviorKind) && <><label className="field-label">Minimum<input aria-label="Behavior minimum" type="number" value={minimum} onChange={(event) => setMinimum(event.target.value)} /></label><label className="field-label">Maximum<input aria-label="Behavior maximum" type="number" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></label></>}</div>
          {(["monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order", "batch_regression_suite"] as string[]).includes(behaviorKind) && <><p className="field-help">Define both cases explicitly. RuFLEX does not infer a pairwise requirement from a single sample.</p><div className="evidence-sample-grid">{run.feature_columns.map((feature) => <label className="field-label" key={`comparison-${feature}`}>Comparison {feature}<input aria-label={`Behavior comparison ${feature}`} type="number" value={comparisonSample[feature] ?? ""} onChange={(event) => setComparisonSample((current) => ({ ...current, [feature]: event.target.value }))} /></label>)}</div></>}
          <Button view="action" disabled={busy || project.read_only || !!behaviorExecutionRecoveryError} onClick={createAndRunBehavior} data-ruflex-action="behavior.run">{busy ? "Running…" : "Create and run BehaviorSpec"}</Button>
          {behaviorExecutionRecoveryError && <div className="error" role="alert" data-testid="behavior-run-recovery"><strong>The BehaviorSpec is already saved; retry its result by the same identity.</strong><p>{behaviorExecutionRecoveryError}</p><Button view="outlined" disabled={busy} onClick={resumeBehaviorSpecExecution}>Retry saved BehaviorSpec</Button></div>}
          {behaviorSpec && <div className="trace-card" data-testid="behavior-spec"><div className="evidence-check-header"><strong>{behaviorSpec.name}</strong><StatusBadge tone="info">{behaviorSpec.kind.replaceAll("_", " ")}</StatusBadge></div><p>{behaviorSpec.rationale}</p><small>{behaviorSpec.run_id ? `Run-bound requirement · ${behaviorSpec.run_id.slice(0, 12)}` : `FIS-bound requirement · ${behaviorSpec.fis_semantic_hash?.slice(0, 12)}`}</small></div>}
          {behaviorResult && <div className="trace-card" data-testid="behavior-result"><div className="evidence-check-header"><strong>{behaviorSpec?.name ?? "Persisted BehaviorSpec"}</strong><StatusBadge tone={behaviorResult.status === "PASS" ? "success" : "danger"}>{behaviorResult.status}</StatusBadge></div><p>{behaviorResult.detail}</p><small>{behaviorResult.run_id ? `Run ${behaviorResult.run_id.slice(0, 12)} · artifact ${behaviorResult.model_artifact_sha256?.slice(0, 12)}` : `FIS revision ${behaviorResult.fis_semantic_hash?.slice(0, 12)}`}</small></div>}
          {lineageBehaviorComparison && <div className="trace-card" data-testid="behavior-revision-comparison"><div className="evidence-check-header"><strong>Persisted revision comparison</strong><StatusBadge tone={lineageBehaviorComparison.regression_detected ? "danger" : "info"}>{lineageBehaviorComparison.transition.replaceAll("_", " ")}</StatusBadge></div><p>{lineageBehaviorComparison.regression_detected ? "A PASS-to-FAIL transition was retained as regression evidence." : "No PASS-to-FAIL regression was observed in this transition."}</p><small>Baseline {lineageBehaviorComparison.baseline_result_id.slice(0, 12)} · candidate {lineageBehaviorComparison.candidate_result_id.slice(0, 12)} · {lineageBehaviorComparison.requirement_identity.slice(0, 16)}</small><p>{lineageBehaviorComparison.scientific_note}</p></div>}
          <section className="trace-card"><strong>Revision transition</strong><p>Compare two executions of the exact same persisted behavior requirement across model or FIS revisions. A PASS → FAIL transition is retained as regression evidence.</p>{behaviorResultsHydrationStatus === "loading" && <p role="status" data-testid="behavior-results-loading">Loading saved BehaviorSpec results…</p>}{behaviorResultsHydrationStatus === "error" && <div className="error" role="alert" data-testid="behavior-results-hydration-error"><strong>Saved BehaviorSpec results could not be verified; comparison is paused.</strong><p>{behaviorResultsHydrationError}</p><Button view="outlined" onClick={() => setBehaviorResultsHydrationReload((current) => current + 1)}>Retry BehaviorSpec results</Button></div>}<div className="training-config-grid"><label className="field-label">Baseline result<select aria-label="Behavior baseline result" value={baselineBehaviorResultId} onChange={(event) => setBaselineBehaviorResultId(event.target.value)}><option value="">Choose result</option>{behaviorResults.map((item) => <option key={item.result_id} value={item.result_id}>{item.result_id.slice(0, 8)} · {item.status}</option>)}</select></label><label className="field-label">Candidate result<select aria-label="Behavior candidate result" value={candidateBehaviorResultId} onChange={(event) => setCandidateBehaviorResultId(event.target.value)}><option value="">Choose result</option>{behaviorResults.map((item) => <option key={item.result_id} value={item.result_id}>{item.result_id.slice(0, 8)} · {item.status}</option>)}</select></label></div><Button view="outlined" disabled={busy || project.read_only || behaviorResultsHydrationStatus !== "available" || behaviorComparisonHydrationStatus === "loading" || behaviorComparisonHydrationStatus === "error" || !baselineBehaviorResultId || !candidateBehaviorResultId || baselineBehaviorResultId === candidateBehaviorResultId} onClick={compareBehaviorRevisions} data-ruflex-action="behavior.revision.compare">Compare revisions</Button>{behaviorComparisonHydrationStatus === "loading" && <p role="status" data-testid="behavior-comparison-loading">Loading saved revision comparison…</p>}{behaviorComparisonHydrationStatus === "none" && <p className="property-description" data-testid="behavior-comparison-empty">No saved revision comparison is available.</p>}{behaviorComparisonHydrationStatus === "error" && <div className="error" role="alert" data-testid="behavior-comparison-hydration-error"><strong>Saved revision comparison could not be verified; creating another comparison is paused.</strong><p>{behaviorComparisonHydrationError}</p><Button view="outlined" onClick={() => setBehaviorComparisonHydrationReload((current) => current + 1)}>Retry saved revision comparison</Button></div>}{behaviorComparison && <p data-testid="behavior-revision-comparison"><strong>{behaviorComparison.transition.replaceAll("_", " ")}</strong> · {behaviorComparison.regression_detected ? "regression retained as evidence" : "no PASS-to-FAIL regression in this transition"}</p>}</section>
        </>}
      </section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">CONDITION MONITORING DEMO</span><h3>Telemetry decision support with review and scope safeguards</h3><p>Telemetry → frozen class/selective policy → scope → explanation check → AssuranceCase → VerificationBundle → ACCEPT / REVIEW / OUT-OF-SCOPE. This is not targeting or actuator control.</p></div><Button view="action" disabled={busy || project.read_only || !run || !selectivePolicy || !["none", "available"].includes(demoHydrationStatus) || generalizationHydrationStatus === "loading" || generalizationHydrationStatus === "error" || generalizationHydrationStatus === "idle"} onClick={runConditionDemo} data-ruflex-action="condition_demo.run">Run telemetry demonstration</Button></div>{demoHydrationStatus === "loading" && <p role="status" data-testid="condition-demo-loading">Loading saved condition-monitoring evidence…</p>}{demoHydrationStatus === "none" && <p className="property-description" data-testid="condition-demo-empty">No saved condition-monitoring result is available.</p>}{demoHydrationStatus === "error" && <div className="error" role="alert" data-testid="condition-demo-hydration-error"><strong>Saved condition-monitoring evidence could not be verified; another demonstration is paused.</strong><p>{demoHydrationError}</p><Button view="outlined" onClick={() => setDemoHydrationReload((current) => current + 1)}>Retry condition-monitoring evidence</Button></div>}{generalizationHydrationStatus === "loading" && <p role="status">Resolving the saved GeneralizationContract before scope-aware review…</p>}{generalizationHydrationStatus === "none" && <p className="property-description">No GeneralizationContract is saved; this demonstration will report scope as undeclared.</p>}{generalizationHydrationStatus === "error" && <div className="error" role="alert" data-testid="evidence-generalization-hydration-error"><strong>Saved GeneralizationContract could not be verified; the scope-aware demonstration is paused.</strong><p>{generalizationHydrationError}</p>{onRetryGeneralization && <Button view="outlined" onClick={onRetryGeneralization}>Retry GeneralizationContract</Button>}</div>}{!selectivePolicy && <p className="property-description">A validation-derived selective policy is required before this demonstration can make an ACCEPT/REVIEW decision.</p>}{demo && <div className="trace-card" data-testid="condition-monitoring-demo"><StatusBadge tone={demo.decision === "ACCEPT" ? "success" : demo.decision === "OUT_OF_SCOPE" ? "danger" : "warning"}>{demo.decision}</StatusBadge><p>Class {demo.predicted_class} · probability {demo.probability.toFixed(4)} · confidence {demo.confidence.toFixed(4)} · scope {demo.scope_disposition}</p><small className="mono">Explanation {demo.explanation_id?.slice(0, 12)} · check {demo.explanation_check_id?.slice(0, 12)} · AssuranceCase {demo.assurance_id?.slice(0, 12)} · VerificationBundle {demo.verification_bundle_sha256?.slice(0, 12)}</small><p>{demo.explanation_note}</p><small>{demo.safety_note}</small></div>}</section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">ASSURANCE CASE</span><h3>Independent evidence gates and qualified claims</h3><p>No universal trust score is produced.</p></div><Button view="action" disabled={busy || project.read_only || evidenceOperationPending} onClick={buildAssurance} data-ruflex-action="assurance.create">{busy ? "Building…" : "Build AssuranceCase"}</Button></div>{evidenceOperationPending && <div className={evidenceOperationPollError ? "error" : "property-description"} role={evidenceOperationPollError ? "alert" : "status"} data-testid="evidence-operation-resume"><strong>{evidenceOperationJob?.kind.replaceAll("_", " ")} · job {evidenceOperationJob?.job_id.slice(0, 12)}</strong>{evidenceOperationPollError ? <p>{evidenceOperationPollError}</p> : <p>This persisted evidence operation is still active; duplicate evidence jobs are paused.</p>}<Button view="outlined" disabled={busy} onClick={resumeEvidenceOperation}>Resume saved evidence job</Button></div>}{assuranceHydrationStatus === "loading" && <p role="status">Loading saved AssuranceCase…</p>}{assuranceHydrationStatus === "none" && !assurance && <p className="property-description" data-testid="assurance-empty">No saved AssuranceCase is available for this project.</p>}{assuranceHydrationStatus === "error" && <div className="error" role="alert"><strong>Saved AssuranceCase could not be verified.</strong><p>{assuranceHydrationError}</p>{onRetryAssurance && <Button view="outlined" onClick={onRetryAssurance}>Retry AssuranceCase</Button>}</div>}{assurance && <div className="trace-card" data-testid="assurance-case"><p>{assurance.scientific_note}</p><div className="data-table-wrap"><table className="data-table"><thead><tr><th>gate</th><th>status</th><th>evidence / risk</th></tr></thead><tbody>{assurance.gates.map((gate) => <tr key={gate.key}><td>{gate.key.replaceAll("_", " ")}</td><td><StatusBadge tone={gate.status === "PASS" ? "success" : gate.status === "FAIL" ? "danger" : "warning"}>{gate.status}</StatusBadge></td><td>{gate.evidence.join(", ") || gate.risk || "—"}</td></tr>)}</tbody></table></div>{assurance.claims.length > 0 && <div className="assurance-claims"><strong>Claim graph</strong>{assurance.claims.map((claim) => <div className="property-description" key={claim.claim_id}><StatusBadge tone={claim.status === "SUPPORTED" ? "success" : claim.status === "UNSUPPORTED" ? "danger" : "warning"}>{claim.status}</StatusBadge><p>{claim.statement}</p><small>Evidence: {claim.evidence_ids.join(", ")}</small>{claim.limitations.map((limitation) => <small key={limitation}>Limitation: {limitation}</small>)}</div>)}</div>}{assurance.unresolved_risks.map((risk) => <p className="property-description" key={risk}>Unresolved risk · {risk}</p>)}</div>}</section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">VERIFICATION BUNDLE</span><h3>Inspection-first evidence export</h3><p>Exports declarative evidence and checksums; it excludes executable code, pickle/joblib, raw datasets, credentials, caches and node_modules.</p></div><Button view="outlined" disabled={busy || project.read_only || !assurance || evidenceOperationPending} onClick={exportBundle} data-ruflex-action="bundle.export">Export and validate bundle</Button></div>{verificationBundleRecord && <div className="trace-card" data-testid="verification-bundle-record"><div className="evidence-check-header"><strong>Persisted VerificationBundle</strong><StatusBadge tone="info">inspection first</StatusBadge></div><p>{verificationBundleRecord.entry_count} declarative entries · SHA-256 {verificationBundleRecord.sha256}</p><small>Manifest {verificationBundleRecord.manifest_sha256} · linked AssuranceCase {verificationBundleRecord.assurance_id}</small></div>}{bundle && <div className="trace-card" data-testid="verification-bundle"><p>{bundle.entry_count} inspection entries · SHA-256 {bundle.sha256}</p><small>{bundle.path}</small>{bundleValidation && <><div className="evidence-check-header"><strong>Portable validation</strong><StatusBadge tone={bundleValidation.status === "PASS" ? "success" : "danger"}>{bundleValidation.status}</StatusBadge></div><p>{bundleValidation.status === "PASS" ? `${bundleValidation.checked_entries} checksummed entries validated after export.` : bundleValidation.errors.join(" ")}</p>{bundleValidation.warnings.map((warning) => <p className="property-description" key={warning}>{warning}</p>)}</>}</div>}</section>
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">EXHAUSTIVE LAB</span><h3>Finite structure and declared discrete-grid evidence</h3><p>Exactness applies only to the finite tree structure or the explicitly declared FIS grid—not to arbitrary continuous models.</p></div></div>
        {exhaustiveHydrationStatus === "loading" && <p role="status">Loading saved exhaustive evidence…</p>}
        {exhaustiveHydrationStatus === "none" && <p className="property-description" data-testid="exhaustive-empty">No saved exhaustive evidence is available.</p>}
        {exhaustiveHydrationStatus === "error" && <div className="error" role="alert" data-testid="exhaustive-hydration-error"><strong>Saved exhaustive evidence could not be verified.</strong><p>{exhaustiveHydrationError}</p>{onRetryExhaustive && <Button view="outlined" onClick={onRetryExhaustive}>Retry exhaustive evidence</Button>}</div>}
        <div className="toolbar-actions">{run?.model_kind === "decision_tree" && <Button view="action" disabled={busy || project.read_only} onClick={() => runExhaustive("decision_tree_structure")} data-ruflex-action="exhaustive.tree.run">Enumerate exact Decision Tree paths</Button>}{evaluation && <><label className="field-label">Grid points/input<input aria-label="Exhaustive grid points" type="number" min="2" max="9" value={gridPoints} onChange={(event) => setGridPoints(event.target.value)} /></label><Button view="outlined" disabled={busy || project.read_only} onClick={() => runExhaustive("fis_discrete_grid")} data-ruflex-action="exhaustive.fis.run">Evaluate declared FIS grid</Button></>}</div>
        {exhaustive && <div className="trace-card" data-testid="exhaustive-result"><StatusBadge tone="info">{exhaustive.exactness_label}</StatusBadge><p>{exhaustive.scientific_note}</p><p>{exhaustive.state_count} enumerated states (preflight estimate {exhaustive.state_estimate}, limit {exhaustive.max_states}) · uncovered {exhaustive.uncovered_states.length} · dead rules on declared grid {exhaustive.dead_rules.length} · overlap states {exhaustive.conflict_states.length}</p>{exhaustive.kind === "decision_tree_structure" && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>leaf</th><th>constraints</th></tr></thead><tbody>{exhaustive.paths.slice(0, 20).map((item, index) => <tr key={index}><td>{String(item.leaf_id)}</td><td>{Array.isArray(item.constraints) ? item.constraints.join("; ") : "—"}</td></tr>)}</tbody></table></div>}{exhaustive.uncovered_states.length > 0 && <p className="property-description">Uncovered/undefined declared states are retained as evidence; they are not silently filled.</p>}</div>}
      </section>
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">CROSS-RUN EXPLANATION REPRODUCIBILITY</span><h3>Compare compatible frozen explanation evidence</h3><p>Prediction reproducibility and post-hoc explanation reproducibility are reported separately.</p></div></div>
        {reproducibilityHydrationStatus === "loading" && <p role="status">Loading saved reproducibility analysis…</p>}
        {reproducibilityHydrationStatus === "none" && <p className="property-description" data-testid="reproducibility-empty">No saved cross-run reproducibility analysis is available.</p>}
        {reproducibilityHydrationStatus === "error" && <div className="error" role="alert" data-testid="reproducibility-hydration-error"><strong>Saved reproducibility analysis could not be verified.</strong><p>{reproducibilityHydrationError}</p>{onRetryReproducibility && <Button view="outlined" onClick={onRetryReproducibility}>Retry reproducibility analysis</Button>}</div>}
        {persistedExplanationsHydrationStatus === "loading" && <p role="status" data-testid="persisted-explanations-loading">Loading saved explanations…</p>}
        {persistedExplanationsHydrationStatus === "error" && <div className="error" role="alert" data-testid="persisted-explanations-hydration-error"><strong>Saved explanations could not be verified; reproducibility comparison is paused.</strong><p>{persistedExplanationsHydrationError}</p><Button view="outlined" onClick={() => setPersistedExplanationsHydrationReload((current) => current + 1)}>Retry saved explanations</Button></div>}
        {reproducibilityRecoveryIds && <div className="error" role="alert" data-testid="reproducibility-recovery"><strong>Reproducibility request outcome is uncertain; resolve the same explanation set before changing it.</strong><p>{reproducibilityRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverReproducibility}>Retry saved comparison lookup</Button>{reproducibilityRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyRestartReproducibility}>Start a new comparison explicitly</Button>}</div>}
        {persistedExplanationsHydrationStatus === "available" && (persistedExplanations.length < 4 ? <EmptyState title="Need persisted explanation cases">Generate the same explanation method for the same declared cases across at least two compatible runs.</EmptyState> : <><div className="comparison-choice">{persistedExplanations.map((item) => <label key={item.explanation_id}><input type="checkbox" disabled={!!reproducibilityRecoveryIds} checked={selectedExplanationIds.includes(item.explanation_id)} onChange={(event) => setSelectedExplanationIds((current) => event.target.checked ? [...current, item.explanation_id] : current.filter((id) => id !== item.explanation_id))} />{item.run_id.slice(0, 8)} · {item.method} · case {item.sample_identity?.slice(-8)}</label>)}</div><Button view="action" disabled={busy || project.read_only || !!reproducibilityRecoveryIds || selectedExplanationIds.length < 4} onClick={compareReproducibility} data-ruflex-action="explanation.reproducibility.compare">{busy ? "Comparing…" : "Compare explanation reproducibility"}</Button></>)}
        {reproducibility && <div className="trace-card" data-testid="reproducibility-result"><p><StatusBadge tone="info">PREDICTION AGREEMENT</StatusBadge> class {(reproducibility.prediction_agreement.class_agreement * 100).toFixed(1)}% · mean |Δ| {reproducibility.prediction_agreement.mean_absolute_difference.toFixed(5)}</p><p><StatusBadge tone="warning">EXPLANATION AGREEMENT</StatusBadge> Spearman {reproducibility.explanation_agreement.mean_spearman?.toFixed(3) ?? "N/A"} · sign {(reproducibility.explanation_agreement.mean_sign_agreement * 100).toFixed(1)}% · top-k {(reproducibility.explanation_agreement.mean_top_k_overlap * 100).toFixed(1)}%</p><div className="data-table-wrap"><table className="data-table"><thead><tr><th>runs</th><th>prediction Δ</th><th>Spearman</th><th>sign</th><th>top-k</th></tr></thead><tbody>{reproducibility.pairwise.map((item) => <tr key={`${item.left_run_id}-${item.right_run_id}`}><td>{item.left_run_id.slice(0, 8)} / {item.right_run_id.slice(0, 8)}</td><td>{item.prediction_mean_absolute_difference.toFixed(5)}</td><td>{item.explanation_spearman?.toFixed(3) ?? "N/A"}</td><td>{(item.explanation_sign_agreement * 100).toFixed(1)}%</td><td>{(item.top_k_overlap * 100).toFixed(1)}%</td></tr>)}</tbody></table></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>feature</th><th>mean attribution</th><th>variability σ</th><th>sign agreement</th></tr></thead><tbody>{reproducibility.per_feature_variability.map((item) => <tr key={item.feature}><td>{item.feature}</td><td>{item.mean_attribution.toFixed(5)}</td><td>{item.standard_deviation.toFixed(5)}</td><td>{(item.sign_agreement * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>{reproducibility.warnings.map((warning) => <p className="property-description" key={warning}>Warning · {warning}</p>)}</div>}
      </section>
    </section>
  );
}
