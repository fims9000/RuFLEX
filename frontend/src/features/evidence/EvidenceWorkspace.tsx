import { useEffect, useMemo, useRef, useState } from "react";
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
  FISSpec,
  PluginDescriptor,
  RunCapabilityNegotiation,
  RuntimeExplainerDescriptor,
  RuntimeValidatorDescriptor,
  ExecutionBackendDescriptor,
  ProductJob,
  ProjectSummary,
  TrainingRun,
  TreePathEvidence,
  TransformPipelineContract,
  studioApi,
} from "../../api";
import { Button, EmptyState, StatusBadge, TextInput } from "../../components/StudioPrimitives";
import { StudioTheme } from "../../design/tokens";
import { ui, uiLanguage } from "../../design/language";
import { BehaviorResultSummary, behaviorName as readableBehaviorName, behaviorKindLabel } from "./BehaviorResultSummary";
import { TraceWorkspace } from "../modelbuild/TraceWorkspace";
import { BehaviorCounterexample } from "./BehaviorCounterexample";
import { BehaviorExactTrace } from "./BehaviorExactTrace";
import { frozenOrdinalCodes } from "../training/frozenOrdinalCodes";

function statusTone(status: ExplanationCheck["status"] | ExplanationCheck["checks"][number]["status"]) {
  if (status === "FAILED" || status === "FAIL") return "danger" as const;
  if (status === "WARNING" || status === "WARN") return "warning" as const;
  if (status === "N/A") return "info" as const;
  return "success" as const;
}

function sameNumericRecord(left: Record<string, number>, right: Record<string, number>) {
  return JSON.stringify(Object.entries(left).sort(([a], [b]) => a.localeCompare(b))) === JSON.stringify(Object.entries(right).sort(([a], [b]) => a.localeCompare(b)));
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "undefined";
}

function formatAttribution(value: number): string {
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  return `${value > 0 ? "+" : "−"}${magnitude < 0.001 ? magnitude.toExponential(2) : magnitude.toFixed(4)}`;
}

function AttributionChart({ explanation }: { explanation: ExplanationContract }) {
  const sorted = [...explanation.attributions].sort((left, right) =>
    Math.abs(right.attribution) - Math.abs(left.attribution) || left.feature.localeCompare(right.feature));
  const maxMagnitude = Math.max(0, ...sorted.map((item) => Math.abs(item.attribution)));
  return <figure className="attribution-chart" data-testid="explanation-attribution-chart">
    <figcaption>{ui("Feature contributions", "Вклад признаков")}</figcaption>
    {sorted[0] && <p data-testid="explanation-readable-summary">{ui(`The largest contribution for this example is ${sorted[0].feature}.`, `На этом примере самый большой вклад у признака «${sorted[0].feature}».`)} {ui("These bars compare contributions within this explanation, not the accuracy of the model.", "Полосы сравнивают вклад признаков в этот прогноз, а не точность модели.")}</p>}
    <p>{ui("Positive values raise the explained output; negative values lower it. This is a local estimate, not a causal effect.", "Плюс повышает показанный выход модели, минус понижает. Это локальная оценка, не доказательство причины.")}</p>
    {sorted.length === 0 ? <p>{ui("No feature contributions were saved.", "Для этого объяснения нет сохранённых вкладов признаков.")}</p> : <div className="attribution-chart-rows">
      {sorted.slice(0, 8).map((item) => <div className="attribution-chart-row" key={item.feature}>
        <span className="attribution-chart-label" title={item.feature}>{item.feature}</span>
        <div className="attribution-chart-track" aria-hidden="true">
          <div className="attribution-chart-half negative">{item.attribution < 0 && <span style={{ width: `${maxMagnitude ? Math.abs(item.attribution) / maxMagnitude * 100 : 0}%` }} />}</div>
          <div className="attribution-chart-half positive">{item.attribution > 0 && <span style={{ width: `${maxMagnitude ? item.attribution / maxMagnitude * 100 : 0}%` }} />}</div>
        </div>
        <span className="attribution-chart-value">{formatAttribution(item.attribution)}</span>
      </div>)}
      {sorted.length > 8 && <p>{ui(`${sorted.length - 8} more features are available in details.`, `Ещё ${sorted.length - 8} признаков — в подробностях.`)}</p>}
    </div>}
  </figure>;
}

export function EvidenceWorkspace({
  project,
  dataset,
  fis,
  modelContextStatus = "loaded",
  modelContextError = null,
  onRetryModelContext,
  run,
  evaluation,
  previousEvaluation,
  treeEvidence,
  treeEvidenceHydrationStatus = "available",
  treeEvidenceHydrationError = null,
  onRetryTreeEvidence,
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
  fis: FISSpec | null;
  modelContextStatus?: "idle" | "loading" | "loaded" | "error";
  modelContextError?: string | null;
  onRetryModelContext?: () => void;
  run: TrainingRun | null;
  evaluation: FISEvaluation | null;
  previousEvaluation: FISEvaluation | null;
  treeEvidence: TreePathEvidence | null;
  treeEvidenceHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  treeEvidenceHydrationError?: string | null;
  onRetryTreeEvidence?: () => void;
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
  const [samplePipeline, setSamplePipeline] = useState<TransformPipelineContract | null>(null);
  const [samplePipelineStatus, setSamplePipelineStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [samplePipelineError, setSamplePipelineError] = useState<string | null>(null);
  const [samplePipelineReload, setSamplePipelineReload] = useState(0);
  const initialFisSample = useMemo(() => Object.fromEntries((fis?.inputs ?? []).map((input) => [input.name, String((input.minimum + input.maximum) / 2)])), [fis?.fis_id, fis?.semantic_hash]);
  const [fisSample, setFisSample] = useState<Record<string, string>>(initialFisSample);
  const [fisComparisonSample, setFisComparisonSample] = useState<Record<string, string>>(initialFisSample);
  const [behaviorSource, setBehaviorSource] = useState<"run" | "fis">(run ? "run" : "fis");
  const [method, setMethod] = useState("occlusion");
  const [busy, setBusy] = useState(false);
  const conditionDemoActionInFlightRef = useRef(false);
  const explanationJobActionInFlightRef = useRef(false);
  const explanationJobCancelInFlightRef = useRef(false);
  const [cancelingExplanationJob, setCancelingExplanationJob] = useState(false);
  const evidenceOperationActionInFlightRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [behaviorKind, setBehaviorKind] = useState<BehaviorSpec["kind"]>("output_range");
  const [behaviorName, setBehaviorName] = useState(ui("Output remains in declared range", "Выход модели в допустимых пределах"));
  const [maximumDelta, setMaximumDelta] = useState("0.1");
  const [minimum, setMinimum] = useState("0");
  const [maximum, setMaximum] = useState("1");
  const [direction, setDirection] = useState<"nondecreasing" | "nonincreasing">("nondecreasing");
  const [behaviorSpec, setBehaviorSpec] = useState<BehaviorSpec | null>(restoredBehaviorSpec);
  const behaviorSpecActionInFlightRef = useRef(false);
  const behaviorComparisonActionInFlightRef = useRef(false);
  const reproducibilityActionInFlightRef = useRef(false);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorSpecResult | null>(restoredBehaviorResult);
  const [behaviorExecutionRecoveryError, setBehaviorExecutionRecoveryError] = useState<string | null>(null);
  const [behaviorSpecCreationRecoveryRequest, setBehaviorSpecCreationRecoveryRequest] = useState<{ payload: Parameters<typeof studioApi.createBehaviorSpec>[1] } | null>(null);
  const [behaviorSpecCreationRecoveryError, setBehaviorSpecCreationRecoveryError] = useState<string | null>(null);
  const [behaviorSpecCreationNotFound, setBehaviorSpecCreationNotFound] = useState(false);
  const [behaviorResults, setBehaviorResults] = useState<BehaviorSpecResult[]>([]);
  const [behaviorResultsHydrationStatus, setBehaviorResultsHydrationStatus] = useState<"loading" | "available" | "error">("loading");
  const [behaviorResultsHydrationError, setBehaviorResultsHydrationError] = useState<string | null>(null);
  const [behaviorResultsHydrationReload, setBehaviorResultsHydrationReload] = useState(0);
  const [behaviorComparison, setBehaviorComparison] = useState<BehaviorRevisionComparison | null>(null);
  const [behaviorComparisonHydrationStatus, setBehaviorComparisonHydrationStatus] = useState<"loading" | "none" | "available" | "error">("loading");
  const [behaviorComparisonHydrationError, setBehaviorComparisonHydrationError] = useState<string | null>(null);
  const [behaviorComparisonHydrationReload, setBehaviorComparisonHydrationReload] = useState(0);
  const [behaviorComparisonRecoveryPair, setBehaviorComparisonRecoveryPair] = useState<{ baselineResultId: string; candidateResultId: string } | null>(null);
  const [behaviorComparisonRecoveryError, setBehaviorComparisonRecoveryError] = useState<string | null>(null);
  const [behaviorComparisonRecoveryNotFound, setBehaviorComparisonRecoveryNotFound] = useState(false);
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
  const [exhaustiveRecoveryRequest, setExhaustiveRecoveryRequest] = useState<{ kind: ExhaustiveLabResult["kind"]; runId: string | null; gridPoints: number; maxStates: number } | null>(null);
  const exhaustiveActionInFlightRef = useRef(false);
  const [exhaustiveRecoveryError, setExhaustiveRecoveryError] = useState<string | null>(null);
  const [exhaustiveRecoveryNotFound, setExhaustiveRecoveryNotFound] = useState(false);
  const [assurance, setAssurance] = useState<AssuranceCase | null>(restoredAssurance);
  const [evidenceOperationJob, setEvidenceOperationJob] = useState<ProductJob | null>(null);
  const [evidenceOperationPollError, setEvidenceOperationPollError] = useState<string | null>(null);
  const [bundle, setBundle] = useState<{ path: string; sha256: string; entry_count: number } | null>(null);
  const [bundleValidation, setBundleValidation] = useState<VerificationBundleValidation | null>(null);
  const [verificationBundleRecord, setVerificationBundleRecord] = useState<VerificationBundle | null>(restoredVerificationBundleRecord);
  const [bundleDownloadPending, setBundleDownloadPending] = useState(false);
  const [bundleDownloadError, setBundleDownloadError] = useState<string | null>(null);
  const [demo, setDemo] = useState<ConditionMonitoringDemo | null>(null);
  const [demoHydrationStatus, setDemoHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [demoHydrationError, setDemoHydrationError] = useState<string | null>(null);
  const [demoHydrationReload, setDemoHydrationReload] = useState(0);
  const [demoRecoveryRequest, setDemoRecoveryRequest] = useState<{ telemetry: Record<string, number>; policyId: string; generalizationContractId: string | null } | null>(null);
  const [demoRecoveryError, setDemoRecoveryError] = useState<string | null>(null);
  const [demoRecoveryNotFound, setDemoRecoveryNotFound] = useState(false);
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
  const categoricalSampleColumns = (run?.feature_columns ?? []).filter((column) => dataset?.profile.columns.some((item) => item.name === column && item.semantic_type === "categorical"));
  useEffect(() => {
    let active = true;
    setSamplePipeline(null);
    if (!run || !categoricalSampleColumns.length) {
      setSamplePipelineStatus("idle");
      setSamplePipelineError(null);
      return () => { active = false; };
    }
    if (!run.transform_pipeline_id || !run.preprocessing_artifact_sha256 || !dataset) {
      setSamplePipelineStatus("error");
      setSamplePipelineError("The selected run has no verifiable TRAIN-frozen categorical encoder.");
      return () => { active = false; };
    }
    setSamplePipelineStatus("loading");
    setSamplePipelineError(null);
    studioApi.getTransformPipeline(project.session_id, run.transform_pipeline_id).then((pipeline) => {
      if (!active) return;
      if (pipeline.pipeline_id !== run.transform_pipeline_id || pipeline.preprocessing_artifact_sha256 !== run.preprocessing_artifact_sha256 || pipeline.dataset_fingerprint !== run.dataset_fingerprint || pipeline.dataset_fingerprint !== dataset.contract.dataset_fingerprint || pipeline.fit_role !== "TRAIN" || JSON.stringify(pipeline.feature_order) !== JSON.stringify(run.feature_columns) || categoricalSampleColumns.some((column) => !frozenOrdinalCodes(pipeline, run)[column])) {
        throw new Error("Saved categorical encoder does not match this TrainingRun and dataset.");
      }
      setSamplePipeline(pipeline);
      setSamplePipelineStatus("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setSamplePipelineStatus("error");
      setSamplePipelineError(reason instanceof Error ? reason.message : "Saved categorical encoder could not be reopened.");
    });
    return () => { active = false; };
  }, [project.session_id, run?.run_id, run?.transform_pipeline_id, run?.preprocessing_artifact_sha256, dataset?.contract.dataset_fingerprint, samplePipelineReload]);
  const sampleOrdinalCodes = frozenOrdinalCodes(samplePipeline, run);
  const categoricalSampleReady = !categoricalSampleColumns.length || (samplePipelineStatus === "loaded" && categoricalSampleColumns.every((column) => Boolean(sampleOrdinalCodes[column])));
  const sampleValue = (feature: string) => categoricalSampleColumns.includes(feature)
    ? (Object.values(sampleOrdinalCodes[feature] ?? {}).includes(Number(sample[feature])) ? sample[feature] : String(Object.values(sampleOrdinalCodes[feature] ?? {})[0] ?? ""))
    : sample[feature] ?? "";
  useEffect(() => { setFisSample(initialFisSample); setFisComparisonSample(initialFisSample); }, [initialFisSample]);
  useEffect(() => {
    if (behaviorSource === "run" && !run && fis) setBehaviorSource("fis");
    if (behaviorSource === "fis" && !fis && run) setBehaviorSource("run");
  }, [behaviorSource, run?.run_id, fis?.fis_id]);
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
    if (!categoricalSampleReady) throw new Error("Load the exact TRAIN-frozen categorical encoder before generating evidence.");
    const result: Record<string, number> = {};
    for (const feature of run.feature_columns) {
      const draft = sampleValue(feature);
      const value = Number(draft);
      if (draft == null || draft.trim() === "" || !Number.isFinite(value)) throw new Error(`${feature} must be a finite number.`);
      result[feature] = value;
    }
    return result;
  }

  function numericComparisonSample() {
    if (!run) throw new Error("Select a trained model run first.");
    const result: Record<string, number> = {};
    for (const feature of run.feature_columns) {
      const draft = comparisonSample[feature];
      const value = Number(draft);
      if (draft == null || draft.trim() === "" || !Number.isFinite(value)) throw new Error(`Comparison ${feature} must be a finite number.`);
      result[feature] = value;
    }
    return result;
  }

  function numericFisBehaviorSample(values: Record<string, string>, comparison = false) {
    if (!fis?.semantic_hash) throw new Error("Save the FIS revision before creating a BehaviorSpec.");
    const result: Record<string, number> = {};
    for (const input of fis.inputs) {
      const draft = values[input.name];
      const value = Number(draft);
      if (draft == null || draft.trim() === "" || !Number.isFinite(value) || value < input.minimum || value > input.maximum) {
        throw new Error(`${comparison ? "Comparison " : ""}${input.name} must be a finite number in [${input.minimum}, ${input.maximum}].`);
      }
      result[input.name] = value;
    }
    return result;
  }

  function numericBehaviorBound(draft: string, label: string) {
    const value = Number(draft);
    if (draft.trim() === "" || !Number.isFinite(value)) throw new Error(`${label} must be a finite number.`);
    return value;
  }

  async function runConditionDemo() {
    if (conditionDemoActionInFlightRef.current) return;
    if (!selectivePolicy) { setError("Create a validation-derived selective policy before running the condition-monitoring demo."); return; }
    if (demoRecoveryRequest) { setError("Resolve the saved condition-monitoring request before starting another demonstration."); return; }
    if (demoHydrationStatus !== "none" && demoHydrationStatus !== "available") { setError("Resolve the saved condition-monitoring evidence before starting another run."); return; }
    if (generalizationHydrationStatus === "loading" || generalizationHydrationStatus === "error" || generalizationHydrationStatus === "idle") {
      setError("Resolve the saved GeneralizationContract state before running the scope-aware condition-monitoring demo.");
      return;
    }
    const request = { telemetry: numericSample(), policyId: selectivePolicy.policy_id, generalizationContractId: generalization?.contract.contract_id ?? null };
    conditionDemoActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try { await submitConditionDemo(request); }
    catch (reason) {
      setDemoRecoveryRequest(request);
      setDemoRecoveryError(reason instanceof Error ? reason.message : "The saved condition-monitoring result could not be confirmed.");
      setDemoRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    }
    finally { conditionDemoActionInFlightRef.current = false; setBusy(false); }
  }

  async function submitConditionDemo(request: { telemetry: Record<string, number>; policyId: string; generalizationContractId: string | null }) {
    const result = await studioApi.runConditionMonitoringDemo(project.session_id, request.telemetry, request.policyId, request.generalizationContractId);
    setDemo(result); setDemoHydrationStatus("available"); setDemoHydrationError(null);
    setDemoRecoveryRequest(null); setDemoRecoveryError(null); setDemoRecoveryNotFound(false);
  }

  async function recoverConditionDemo() {
    if (conditionDemoActionInFlightRef.current) return;
    const request = demoRecoveryRequest;
    if (!request) return;
    conditionDemoActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      let result: ConditionMonitoringDemo;
      try { result = await studioApi.getLatestConditionMonitoringDemo(project.session_id); }
      catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) {
          setDemoRecoveryNotFound(true);
          setDemoRecoveryError("No persisted result is visible yet. Retry lookup later, or explicitly rerun the saved request if it did not finish.");
          return;
        }
        throw reason;
      }
      if (result.policy_id !== request.policyId || !sameNumericRecord(result.telemetry, request.telemetry) || (result.generalization_contract_id ?? null) !== request.generalizationContractId) {
        throw new Error("The latest saved demonstration belongs to different inputs or policy; no replacement was created.");
      }
      setDemo(result); setDemoHydrationStatus("available"); setDemoHydrationError(null);
      setDemoRecoveryRequest(null); setDemoRecoveryError(null); setDemoRecoveryNotFound(false);
    } catch (reason) {
      setDemoRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact condition-monitoring result.");
      setDemoRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { conditionDemoActionInFlightRef.current = false; setBusy(false); }
  }

  async function explicitlyRestartConditionDemo() {
    if (conditionDemoActionInFlightRef.current) return;
    if (!demoRecoveryRequest || !demoRecoveryNotFound) return;
    conditionDemoActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try { await submitConditionDemo(demoRecoveryRequest); }
    catch (reason) {
      setDemoRecoveryError(reason instanceof Error ? reason.message : "The replacement demonstration could not be confirmed.");
      setDemoRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { conditionDemoActionInFlightRef.current = false; setBusy(false); }
  }

  async function generate() {
    if (explanationJobActionInFlightRef.current || !run || explanationJobHydrationStatus === "loading" || explanationJobHydrationStatus === "error" || explanationJobPollError || explanationJob && ["queued", "running"].includes(explanationJob.status)) return;
    explanationJobActionInFlightRef.current = true;
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
      explanationJobActionInFlightRef.current = false;
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
    if (explanationJobActionInFlightRef.current || !explanationJob || (!["queued", "running"].includes(explanationJob.status) && !explanationJobPollError)) return;
    explanationJobActionInFlightRef.current = true;
    setBusy(true);
    setError(null);
    setExplanationJobPollError(null);
    try {
      await completeExplanationJob(explanationJob);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      explanationJobActionInFlightRef.current = false;
      setBusy(false);
    }
  }

  async function check() {
    if (explanationJobActionInFlightRef.current || !explanation || explanationJobHydrationStatus === "loading" || explanationJobHydrationStatus === "error" || explanationJobPollError || explanationJob && ["queued", "running"].includes(explanationJob.status)) return;
    explanationJobActionInFlightRef.current = true;
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
      explanationJobActionInFlightRef.current = false;
      setBusy(false);
    }
  }
  async function cancelQueuedJob() {
    if (explanationJobCancelInFlightRef.current || !explanationJob || explanationJob.status !== "queued") return;
    explanationJobCancelInFlightRef.current = true;
    setCancelingExplanationJob(true);
    setError(null);
    try { setExplanationJob(await studioApi.cancelEvidenceJob(project.session_id, explanationJob.job_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally {
      explanationJobCancelInFlightRef.current = false;
      setCancelingExplanationJob(false);
    }
  }

  async function createAndRunBehavior() {
    if (behaviorSpecActionInFlightRef.current || behaviorSpecCreationRecoveryRequest || (behaviorSource === "run" ? !run : !fis?.semantic_hash)) return;
    behaviorSpecActionInFlightRef.current = true;
    setBusy(true); setError(null);
    let createdSpec: BehaviorSpec | null = null;
    let request: { payload: Parameters<typeof studioApi.createBehaviorSpec>[1] } | null = null;
    try {
      const numeric = behaviorSource === "fis" ? numericFisBehaviorSample(fisSample) : numericSample();
      const pairKinds = ["monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order", "batch_regression_suite"];
      const rangeKinds = ["output_range", "regression_case", "domain_constraint", "forbidden_region", "batch_regression_suite"];
      const pair = pairKinds.includes(behaviorKind) ? (behaviorSource === "fis" ? numericFisBehaviorSample(fisComparisonSample, true) : numericComparisonSample()) : null;
      const lower = rangeKinds.includes(behaviorKind) ? numericBehaviorBound(minimum, "Behavior minimum") : null;
      const upper = rangeKinds.includes(behaviorKind) ? numericBehaviorBound(maximum, "Behavior maximum") : null;
      if (lower !== null && upper !== null && lower > upper) throw new Error("Behavior minimum must not exceed maximum.");
      const delta = behaviorKind === "bounded_perturbation" ? numericBehaviorBound(maximumDelta, "Behavior maximum delta") : null;
      if (delta !== null && delta < 0) throw new Error("Behavior maximum delta must be nonnegative.");
      request = { payload: {
        run_id: behaviorSource === "run" ? run!.run_id : null,
        fis_id: behaviorSource === "fis" ? fis!.fis_id : null,
        fis_semantic_hash: behaviorSource === "fis" ? fis!.semantic_hash : null,
        name: behaviorName, kind: behaviorKind, sample: numeric, comparison_sample: pair,
        minimum: lower,
        maximum: upper,
        expected_direction: ["monotonic_pair", "required_order"].includes(behaviorKind) ? direction : null,
        maximum_delta: delta,
        cases: behaviorKind === "batch_regression_suite" ? [{ name: "primary", sample: numeric, minimum: lower, maximum: upper }, { name: "comparison", sample: pair ?? numeric, minimum: lower, maximum: upper }] : [],
        tolerance: 1e-9, rationale: "Persisted engineering behavior requirement.",
      } };
      const created = await studioApi.createBehaviorSpec(project.session_id, request.payload);
      createdSpec = created;
      setBehaviorSpec(created);
      setBehaviorSpecCreationRecoveryRequest(null); setBehaviorSpecCreationRecoveryError(null); setBehaviorSpecCreationNotFound(false);
      setBehaviorExecutionRecoveryError(null);
      const result = await studioApi.runBehaviorSpec(project.session_id, created.spec_id);
      setBehaviorResult(result); onBehaviorResult(result); setBehaviorResultsHydrationReload((current) => current + 1);
    } catch (reason) {
      if (createdSpec) setBehaviorExecutionRecoveryError(reason instanceof Error ? reason.message : "The saved BehaviorSpec result could not be confirmed.");
      else if (request) {
        setBehaviorSpecCreationRecoveryRequest(request);
        setBehaviorSpecCreationRecoveryError(reason instanceof Error ? reason.message : "The saved BehaviorSpec could not be confirmed.");
        setBehaviorSpecCreationNotFound(false);
      }
      setError(reason instanceof Error ? reason.message : String(reason));
    }
    finally { behaviorSpecActionInFlightRef.current = false; setBusy(false); }
  }

  async function recoverBehaviorSpecCreation() {
    if (behaviorSpecActionInFlightRef.current) return;
    const request = behaviorSpecCreationRecoveryRequest;
    if (!request) return;
    behaviorSpecActionInFlightRef.current = true;
    let matchedSpec = false;
    setBusy(true); setError(null);
    try {
      const specs = await studioApi.listBehaviorSpecs(project.session_id);
      const fields = ["name", "kind", "sample", "comparison_sample", "minimum", "maximum", "expected_direction", "maximum_delta", "cases", "tolerance", "rationale"] as const;
      const created = specs.find((item) => item.run_id === request.payload.run_id && item.fis_id === request.payload.fis_id && item.fis_semantic_hash === request.payload.fis_semantic_hash && fields.every((field) => canonicalJson(item[field]) === canonicalJson(request.payload[field])));
      if (!created) {
        setBehaviorSpecCreationNotFound(true);
        setBehaviorSpecCreationRecoveryError("No saved requirement with this exact model revision and definition is visible yet. Retry lookup later, or explicitly repeat creation if the original request did not finish.");
        return;
      }
      matchedSpec = true;
      setBehaviorSpec(created); setBehaviorSpecCreationRecoveryRequest(null); setBehaviorSpecCreationRecoveryError(null); setBehaviorSpecCreationNotFound(false);
      const results = await studioApi.listBehaviorResults(project.session_id);
      const result = results.find((item) => item.spec_id === created.spec_id) ?? await studioApi.runBehaviorSpec(project.session_id, created.spec_id);
      setBehaviorResult(result); onBehaviorResult(result); setBehaviorResultsHydrationReload((current) => current + 1);
      setBehaviorExecutionRecoveryError(null);
    } catch (reason) {
      if (!matchedSpec) setBehaviorSpecCreationRecoveryError(reason instanceof Error ? reason.message : "Could not recover the saved BehaviorSpec.");
      else setBehaviorExecutionRecoveryError(reason instanceof Error ? reason.message : "The saved BehaviorSpec was found, but its result could not be confirmed.");
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { behaviorSpecActionInFlightRef.current = false; setBusy(false); }
  }

  async function explicitlyRestartBehaviorSpecCreation() {
    if (behaviorSpecActionInFlightRef.current) return;
    const request = behaviorSpecCreationRecoveryRequest;
    if (!request || !behaviorSpecCreationNotFound) return;
    behaviorSpecActionInFlightRef.current = true;
    let createdSpec = false;
    setBusy(true); setError(null);
    try {
      const created = await studioApi.createBehaviorSpec(project.session_id, request.payload);
      createdSpec = true;
      setBehaviorSpec(created); setBehaviorSpecCreationRecoveryRequest(null); setBehaviorSpecCreationRecoveryError(null); setBehaviorSpecCreationNotFound(false);
      setBehaviorExecutionRecoveryError(null);
      const result = await studioApi.runBehaviorSpec(project.session_id, created.spec_id);
      setBehaviorResult(result); onBehaviorResult(result); setBehaviorResultsHydrationReload((current) => current + 1);
    } catch (reason) {
      if (createdSpec) setBehaviorExecutionRecoveryError(reason instanceof Error ? reason.message : "The newly saved BehaviorSpec result could not be confirmed.");
      else { setBehaviorSpecCreationRecoveryError(reason instanceof Error ? reason.message : "The repeated BehaviorSpec creation could not be confirmed."); setBehaviorSpecCreationNotFound(false); }
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { behaviorSpecActionInFlightRef.current = false; setBusy(false); }
  }

  async function resumeBehaviorSpecExecution() {
    if (behaviorSpecActionInFlightRef.current || !behaviorSpec) return;
    behaviorSpecActionInFlightRef.current = true;
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
    } finally { behaviorSpecActionInFlightRef.current = false; setBusy(false); }
  }

  async function compareBehaviorRevisions() {
    if (behaviorComparisonActionInFlightRef.current || behaviorComparisonRecoveryPair || !baselineBehaviorResultId || !candidateBehaviorResultId) return;
    const pair = { baselineResultId: baselineBehaviorResultId, candidateResultId: candidateBehaviorResultId };
    behaviorComparisonActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      await submitBehaviorRevisionComparison(pair);
    } catch (reason) {
      setBehaviorComparisonRecoveryPair(pair);
      setBehaviorComparisonRecoveryError(reason instanceof Error ? reason.message : "The saved revision comparison could not be confirmed.");
      setBehaviorComparisonRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : "Could not compare BehaviorSpec revisions");
    }
    finally { behaviorComparisonActionInFlightRef.current = false; setBusy(false); }
  }

  async function submitBehaviorRevisionComparison(pair: { baselineResultId: string; candidateResultId: string }) {
    const result = await studioApi.compareBehaviorResults(project.session_id, pair.baselineResultId, pair.candidateResultId);
    setBehaviorComparison(result); setBehaviorComparisonHydrationStatus("available"); setBehaviorComparisonHydrationError(null);
    setBehaviorComparisonRecoveryPair(null); setBehaviorComparisonRecoveryError(null); setBehaviorComparisonRecoveryNotFound(false);
  }

  async function recoverBehaviorRevisionComparison() {
    if (behaviorComparisonActionInFlightRef.current) return;
    const pair = behaviorComparisonRecoveryPair;
    if (!pair) return;
    behaviorComparisonActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      const comparisons = await studioApi.listBehaviorRevisionComparisons(project.session_id);
      const result = comparisons.find((item) => item.baseline_result_id === pair.baselineResultId && item.candidate_result_id === pair.candidateResultId);
      if (!result) {
        setBehaviorComparisonRecoveryNotFound(true);
        setBehaviorComparisonRecoveryError("No saved comparison for this exact result pair is visible yet. Retry lookup later, or explicitly repeat the comparison if the original request did not finish.");
        return;
      }
      setBehaviorComparison(result); setBehaviorComparisonHydrationStatus("available"); setBehaviorComparisonHydrationError(null);
      setBehaviorComparisonRecoveryPair(null); setBehaviorComparisonRecoveryError(null); setBehaviorComparisonRecoveryNotFound(false);
    } catch (reason) {
      setBehaviorComparisonRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact revision comparison.");
      setBehaviorComparisonRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { behaviorComparisonActionInFlightRef.current = false; setBusy(false); }
  }

  async function explicitlyRestartBehaviorRevisionComparison() {
    if (behaviorComparisonActionInFlightRef.current) return;
    if (!behaviorComparisonRecoveryPair || !behaviorComparisonRecoveryNotFound) return;
    behaviorComparisonActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try { await submitBehaviorRevisionComparison(behaviorComparisonRecoveryPair); }
    catch (reason) {
      setBehaviorComparisonRecoveryError(reason instanceof Error ? reason.message : "The replacement comparison could not be confirmed.");
      setBehaviorComparisonRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { behaviorComparisonActionInFlightRef.current = false; setBusy(false); }
  }

  async function compareReproducibility() {
    if (reproducibilityActionInFlightRef.current || reproducibilityRecoveryIds || selectedExplanationIds.length < 4) return;
    reproducibilityActionInFlightRef.current = true;
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
    finally { reproducibilityActionInFlightRef.current = false; setBusy(false); }
  }

  async function submitReproducibility(explanationIds: string[]) {
    const result = await studioApi.createExplanationReproducibility(project.session_id, explanationIds);
    setReproducibility(result); onReproducibility(result);
    setReproducibilityRecoveryIds(null);
    setReproducibilityRecoveryError(null);
    setReproducibilityRecoveryNotFound(false);
  }

  async function recoverReproducibility() {
    if (reproducibilityActionInFlightRef.current) return;
    if (!reproducibilityRecoveryIds) return;
    reproducibilityActionInFlightRef.current = true;
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
    } finally { reproducibilityActionInFlightRef.current = false; setBusy(false); }
  }

  async function explicitlyRestartReproducibility() {
    if (reproducibilityActionInFlightRef.current) return;
    if (!reproducibilityRecoveryIds || !reproducibilityRecoveryNotFound) return;
    reproducibilityActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      await submitReproducibility(reproducibilityRecoveryIds);
    } catch (reason) {
      setReproducibilityRecoveryError(reason instanceof Error ? reason.message : "The replacement comparison could not be confirmed.");
      setReproducibilityRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { reproducibilityActionInFlightRef.current = false; setBusy(false); }
  }

  async function submitExhaustive(request: { kind: ExhaustiveLabResult["kind"]; runId: string | null; gridPoints: number; maxStates: number }) {
    const result = await studioApi.runExhaustiveLab(project.session_id, request.kind, request.runId, request.gridPoints, request.maxStates);
    setExhaustive(result); onExhaustive(result);
    setExhaustiveRecoveryRequest(null); setExhaustiveRecoveryError(null); setExhaustiveRecoveryNotFound(false);
  }

  async function runExhaustive(kind: ExhaustiveLabResult["kind"]) {
    if (exhaustiveActionInFlightRef.current || exhaustiveRecoveryRequest) return;
    const request = { kind, runId: kind === "decision_tree_structure" ? run?.run_id ?? null : null, gridPoints: Number(gridPoints), maxStates: 10000 };
    exhaustiveActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try { await submitExhaustive(request); }
    catch (reason) {
      setExhaustiveRecoveryRequest(request);
      setExhaustiveRecoveryError(reason instanceof Error ? reason.message : "The exhaustive result could not be confirmed.");
      setExhaustiveRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { exhaustiveActionInFlightRef.current = false; setBusy(false); }
  }

  async function recoverExhaustive() {
    if (exhaustiveActionInFlightRef.current) return;
    const request = exhaustiveRecoveryRequest;
    if (!request) return;
    exhaustiveActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try {
      let result: ExhaustiveLabResult;
      try { result = await studioApi.getLatestExhaustiveLab(project.session_id); }
      catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) {
          setExhaustiveRecoveryNotFound(true);
          setExhaustiveRecoveryError("No persisted exhaustive result is visible yet. Retry lookup later, or explicitly rerun the saved request if it did not finish.");
          return;
        }
        throw reason;
      }
      const matches = result.kind === request.kind && (request.kind === "decision_tree_structure"
        ? result.run_id === request.runId
        : result.requested_grid_points === request.gridPoints && result.max_states === request.maxStates);
      if (!matches) throw new Error("The latest saved exhaustive result belongs to a different request; no replacement was created.");
      setExhaustive(result); onExhaustive(result);
      setExhaustiveRecoveryRequest(null); setExhaustiveRecoveryError(null); setExhaustiveRecoveryNotFound(false);
    } catch (reason) {
      setExhaustiveRecoveryError(reason instanceof Error ? reason.message : "Could not recover the exact saved exhaustive result.");
      setExhaustiveRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { exhaustiveActionInFlightRef.current = false; setBusy(false); }
  }

  async function explicitlyRestartExhaustive() {
    if (exhaustiveActionInFlightRef.current) return;
    if (!exhaustiveRecoveryRequest || !exhaustiveRecoveryNotFound) return;
    exhaustiveActionInFlightRef.current = true;
    setBusy(true); setError(null);
    try { await submitExhaustive(exhaustiveRecoveryRequest); }
    catch (reason) {
      setExhaustiveRecoveryError(reason instanceof Error ? reason.message : "The replacement exhaustive request could not be confirmed.");
      setExhaustiveRecoveryNotFound(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { exhaustiveActionInFlightRef.current = false; setBusy(false); }
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
      if (!exported.path || !exported.sha256 || !job.output.bundle_id || !Number.isFinite(exported.entry_count)) throw new Error("VerificationBundle job did not persist a complete export receipt.");
      setBundle(exported);
      setBundleValidation(await studioApi.validateVerificationBundle(exported.path));
      setVerificationBundleRecord(await studioApi.getVerificationBundle(project.session_id, job.output.bundle_id));
      return;
    }
    throw new Error(`Unsupported persisted evidence operation kind: ${job.kind}`);
  }
  async function resumeEvidenceOperation() {
    if (evidenceOperationActionInFlightRef.current || !evidenceOperationJob || !["queued", "running"].includes(evidenceOperationJob.status)) return;
    evidenceOperationActionInFlightRef.current = true;
    setBusy(true); setError(null); setEvidenceOperationPollError(null);
    try {
      const job = await waitForEvidenceOperation(evidenceOperationJob);
      if (job.status === "succeeded") await applyEvidenceOperationResult(job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { evidenceOperationActionInFlightRef.current = false; setBusy(false); }
  }
  async function buildAssurance() {
    if (evidenceOperationActionInFlightRef.current || evidenceOperationPending) return;
    evidenceOperationActionInFlightRef.current = true;
    setBusy(true); setError(null); setEvidenceOperationPollError(null);
    try {
      const job = await waitForEvidenceOperation(await studioApi.startAssuranceCaseJob(project.session_id, executionBackendKey));
      if (job.status === "succeeded") await applyEvidenceOperationResult(job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { evidenceOperationActionInFlightRef.current = false; setBusy(false); }
  }
  async function exportBundle() {
    if (evidenceOperationActionInFlightRef.current || evidenceOperationPending) return;
    evidenceOperationActionInFlightRef.current = true;
    setBusy(true); setError(null); setEvidenceOperationPollError(null);
    try {
      const job = await waitForEvidenceOperation(await studioApi.startVerificationBundleJob(project.session_id, executionBackendKey));
      if (job.status === "succeeded") await applyEvidenceOperationResult(job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { evidenceOperationActionInFlightRef.current = false; setBusy(false); }
  }

  async function downloadBundle() {
    if (!verificationBundleRecord || bundleDownloadPending) return;
    setBundleDownloadPending(true); setBundleDownloadError(null);
    try {
      const blob = await studioApi.downloadVerificationBundle(project.session_id, verificationBundleRecord.bundle_id);
      const url = URL.createObjectURL(blob);
      try {
        const link = document.createElement("a");
        link.href = url;
        link.download = `ruflex-verification-bundle-${verificationBundleRecord.bundle_id}.zip`;
        document.body.appendChild(link);
        link.click();
        link.remove();
      } finally { setTimeout(() => URL.revokeObjectURL(url), 60_000); }
    } catch (reason) { setBundleDownloadError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBundleDownloadPending(false); }
  }

  const hasExact = Boolean(evaluation || treeEvidence);
  const evidenceOperationPending = Boolean(evidenceOperationJob && ["queued", "running"].includes(evidenceOperationJob.status));

  return (
    <section className="evidence-workbench">
      <div className="feature-toolbar">
        <div>
          <span className="eyebrow">{ui("EVIDENCE WORKBENCH", "ДОКАЗАТЕЛЬСТВА")}</span>
          <h2>{ui("Computation evidence and post-hoc attribution", "Вычисления и объяснения")}</h2>
          <p>{ui("Exact computation, structural execution and post-hoc attribution remain separate scientific objects.", "Точный ход вычисления и объяснение модели показаны отдельно.")}</p>
        </div>
        <div className="evidence-label-row">
          {evaluation && <StatusBadge tone="success">{ui("EXACT COMPUTATION", "ТОЧНОЕ ВЫЧИСЛЕНИЕ")}</StatusBadge>}
          {treeEvidence && <StatusBadge tone="success">{ui("STRUCTURAL TRACE", "ТРАССА ДЕРЕВА")}</StatusBadge>}
          {explanation && <StatusBadge tone="warning">{ui("POST-HOC ATTRIBUTION", "ОБЪЯСНЕНИЕ")}</StatusBadge>}
        </div>
      </div>

      {treeEvidenceHydrationStatus === "loading" && <p role="status">{ui("Checking saved structural trace…", "Проверка сохранённой трассы…")}</p>}
      {treeEvidenceHydrationStatus === "none" && !explanation && <p className="property-description" data-testid="tree-evidence-empty">{ui("No saved structural tree trace is available for this project.", "Сохранённой трассы дерева пока нет.")}</p>}
      {treeEvidenceHydrationStatus === "error" && <div className="error" role="alert" data-testid="tree-evidence-hydration-error"><strong>{ui("Saved structural trace could not be verified.", "Не удалось проверить сохранённый путь вычисления.")}</strong><p>{treeEvidenceHydrationError}</p>{onRetryTreeEvidence && <Button view="outlined" onClick={onRetryTreeEvidence}>{ui("Retry structural trace", "Повторить загрузку пути")}</Button>}</div>}

      {hasExact && (
        <section className="evidence-section">
          <TraceWorkspace evaluation={evaluation} previousEvaluation={previousEvaluation} treeEvidence={treeEvidence} theme={theme} />
        </section>
      )}

      <section className="evidence-section posthoc-panel">
        <div className="feature-toolbar compact-toolbar">
          <div>
            <span className="eyebrow">{ui("POST-HOC ATTRIBUTION", "ОБЪЯСНЕНИЕ ПРОГНОЗА")}</span>
            <h3>{method === "occlusion" ? ui("Train-reference occlusion", "Влияние признаков · Occlusion") : method === "integrated_gradients" ? ui("Integrated Gradients", "Интегрированные градиенты") : method === "gradient_shap" ? "GradientSHAP" : method === "tree_shap" ? "TreeSHAP" : ui("SHAP · permutation", "SHAP · перестановки")}</h3>
            <p>{ui(`${method === "occlusion" ? "One feature at a time is replaced by its train-derived reference." : method === "integrated_gradients" ? "Gradients are integrated from a train-derived reference to the observed sample." : method === "gradient_shap" ? "Expected gradients use a deterministic train-only background." : method === "tree_shap" ? "TreeSHAP uses the persisted declarative tree ensemble and a deterministic train-only background." : "Permutation SHAP uses the persisted model through a deterministic train-only background."} This is not a causal effect or an exact trace.`, "Объяснение строится по сохранённой модели и обучающим данным. Это не причинный вывод.")}</p>
          </div>
        </div>
        {explanationHydrationStatus === "loading" && <p role="status">{ui("Loading saved explanation…", "Загрузка объяснения…")}</p>}
        {explanationHydrationStatus === "none" && <p className="property-description" data-testid="explanation-empty">{ui("No saved explanation is available for this project.", "Сохранённого объяснения пока нет.")}</p>}
        {explanationHydrationStatus === "error" && <div className="error" role="alert" data-testid="explanation-hydration-error"><strong>{ui("Saved explanation could not be verified.", "Не удалось проверить сохранённое объяснение.")}</strong><p>{explanationHydrationError}</p>{onRetryExplanation && <Button view="outlined" onClick={onRetryExplanation}>{ui("Retry saved explanation", "Повторить загрузку объяснения")}</Button>}</div>}
        {!run ? (
          <EmptyState title={ui("No trained model selected", "Модель не выбрана")}>{ui("Train or reopen a catalog model to generate a local attribution.", "Обучите модель или откройте сохранённый запуск.")}</EmptyState>
        ) : (
          <>
            <label className="field-label evidence-method-select">{ui("Method", "Метод")}
              <select aria-label={ui("Explanation method", "Метод объяснения")} value={method} disabled={capabilityHydrationStatus !== "available"} onChange={(event) => setMethod(event.target.value)}>
                {selectableMethods.map((candidate) => <option value={candidate} key={candidate}>{candidate === "occlusion" ? "Occlusion" : candidate === "shap" ? "SHAP · permutation" : candidate === "tree_shap" ? "TreeSHAP" : candidate === "integrated_gradients" ? "Integrated Gradients" : candidate === "gradient_shap" ? "GradientSHAP" : `${candidate} · runtime explainer`}</option>)}
              </select>
            </label>
            <details open={uiLanguage === "en"}><summary>{ui("Execution details", "Технические настройки")}</summary>            <label className="field-label evidence-method-select">{ui("Execution backend", "Среда выполнения")}<select aria-label={ui("Evidence execution backend", "Среда выполнения объяснения")} value={executionBackendKey} disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !executionBackends.length} onChange={(event) => setExecutionBackendKey(event.target.value)}>{executionBackends.map((backend) => <option key={backend.identity.key} value={backend.identity.key}>{backend.identity.key} · {backend.identity.provider}</option>)}</select></label></details>
            <details className="evidence-advanced-details">
              <summary>{ui("Change the explained input", "Изменить значения для объяснения")}</summary>
              <div className="evidence-sample-grid">
              {run.feature_columns.map((feature) => (
                <label className="field-label" key={feature}>
                  {feature}
                  {categoricalSampleColumns.includes(feature) ? <select aria-label={`Evidence ${feature}`} value={sampleValue(feature)} disabled={!categoricalSampleReady || busy} onChange={(event) => setSample((current) => ({ ...current, [feature]: event.target.value }))}>
                    {Object.entries(sampleOrdinalCodes[feature] ?? {}).map(([label, code]) => <option key={label} value={code}>{label}</option>)}
                  </select> : <TextInput aria-label={`Evidence ${feature}`} value={sample[feature] ?? ""} onUpdate={(value) => setSample((current) => ({ ...current, [feature]: value }))} />}
                </label>
              ))}
              </div>
            </details>
            {samplePipelineStatus === "loading" && <p role="status">{ui("Loading this run’s TRAIN-frozen categorical choices…", "Загрузка вариантов категорий для этой модели…")}</p>}
            {samplePipelineStatus === "error" && <div className="error" role="alert"><strong>{ui("Categorical evidence input is paused.", "Ввод категорий временно недоступен.")}</strong><p>{samplePipelineError}</p><Button view="outlined" onClick={() => setSamplePipelineReload((current) => current + 1)}>{ui("Retry categorical encoder", "Повторить загрузку категорий")}</Button></div>}
            <div className="evidence-actions">
              <Button view="action" disabled={busy || project.read_only || !categoricalSampleReady || runtimeCatalogHydrationStatus !== "available" || !executionBackends.length || capabilityHydrationStatus !== "available" || selectableMethods.length === 0 || explanationJobHydrationStatus === "loading" || explanationJobHydrationStatus === "error" || !!explanationJobPollError || !!explanationJob && ["queued", "running"].includes(explanationJob.status)} onClick={generate} data-ruflex-action="explanation.generate">{busy ? ui("Generating…", "Построение…") : ui("Generate explanation", "Построить объяснение")}</Button>
              <span className="property-description">{ui("Model", "Модель")}: {run.model_kind}</span>
            </div>
            {capabilityNegotiation && <details className="evidence-advanced-details" data-testid="run-capability-negotiation"><summary>{ui("Method availability", "Доступность методов")}</summary><div className="property-list">{capabilityNegotiation.decisions.map((decision) => <div key={decision.capability}><span>{decision.capability.replaceAll("_", " ")}</span><span><StatusBadge tone={decision.status === "AVAILABLE" ? "success" : "info"}>{decision.status}</StatusBadge> {decision.detail}</span></div>)}</div></details>}
            {capabilityHydrationStatus === "loading" && <p role="status" data-testid="run-capability-loading">{ui("Checking explainer support for this exact run…", "Проверка доступных методов объяснения…")}</p>}
            {capabilityHydrationStatus === "error" && <div className="error" role="alert" data-testid="run-capability-error"><strong>{ui("Explainer support for this run could not be verified; generation is paused.", "Не удалось проверить методы объяснения. Создание пока недоступно.")}</strong><p>{capabilityHydrationError}</p><Button view="outlined" onClick={() => setCapabilityHydrationReload((current) => current + 1)}>{ui("Retry run capabilities", "Повторить проверку методов")}</Button></div>}
            {runtimeCatalogHydrationStatus === "loading" && <p role="status" data-testid="runtime-catalog-loading">{ui("Loading runtime explainer, validator and execution-backend catalogs…", "Загрузка методов объяснения и проверок…")}</p>}
            {runtimeCatalogHydrationStatus === "error" && <div className="error" role="alert" data-testid="runtime-catalog-error"><strong>{ui("Runtime catalogs could not be verified; evidence jobs are paused.", "Не удалось загрузить методы. Операции временно недоступны.")}</strong><p>{runtimeCatalogHydrationError}</p><Button view="outlined" onClick={() => setRuntimeCatalogHydrationReload((current) => current + 1)}>{ui("Retry runtime catalogs", "Повторить загрузку методов")}</Button></div>}
            {runtimeCatalogHydrationStatus === "available" && !executionBackends.length && <p className="property-description" data-testid="runtime-backends-empty">{ui("No execution backend is available; evidence jobs cannot be started.", "Нет доступной среды выполнения.")}</p>}
            {explanationJobHydrationStatus === "loading" && <p role="status" data-testid="explanation-job-loading">{ui("Loading saved explanation job…", "Загрузка сохранённой задачи…")}</p>}
            {explanationJobHydrationStatus === "none" && <p className="property-description" data-testid="explanation-job-empty">{ui("No saved explanation job is available.", "Сохранённых задач объяснения нет.")}</p>}
            {explanationJobHydrationStatus === "error" && <div className="error" role="alert" data-testid="explanation-job-hydration-error"><strong>{ui("Saved explanation job could not be verified; starting another operation is paused.", "Не удалось проверить задачу. Новый запуск временно недоступен.")}</strong><p>{explanationJobHydrationError}</p><Button view="outlined" onClick={() => setExplanationJobHydrationReload((current) => current + 1)}>{ui("Retry saved explanation job", "Повторить загрузку задачи")}</Button></div>}
            {explanationJob && <div className="property-description" data-testid="explanation-job">{explanationJob.status === "succeeded" ? <><StatusBadge tone="success">{explanationJob.kind === "explanation_generation" ? ui("Explanation saved", "Объяснение сохранено") : ui("Check saved", "Проверка сохранена")}</StatusBadge><details className="evidence-job-details"><summary>{ui("Job details", "Сведения о задаче")}</summary><span>{explanationJob.status.toUpperCase()} · {explanationJob.execution_backend_key ?? "frozen execution backend"} · {explanationJob.message ?? "Persisted operation"} · job {explanationJob.job_id.slice(0, 12)}</span></details></> : <><StatusBadge tone={explanationJob.status === "failed" ? "danger" : "warning"}>{explanationJob.status.toUpperCase()}</StatusBadge> {explanationJob.execution_backend_key ?? "frozen execution backend"} · {explanationJob.message ?? "Persisted operation"} · job {explanationJob.job_id.slice(0, 12)}{explanationJob.error && ` · ${explanationJob.error}`}{explanationJob.status === "queued" && <Button view="flat" size="s" disabled={cancelingExplanationJob} onClick={cancelQueuedJob} data-ruflex-action="explanation.cancel">{cancelingExplanationJob ? "Cancelling…" : "Cancel queued job"}</Button>}</>}</div>}
            {explanationJob && (["queued", "running"].includes(explanationJob.status) || !!explanationJobPollError) && <div className={explanationJobPollError ? "error" : "property-description"} role={explanationJobPollError ? "alert" : "status"} data-testid="explanation-job-resume">{explanationJobPollError ? <><strong>{explanationJob.status === "succeeded" ? "Saved job output needs recovery." : "Saved job status needs recovery."}</strong><p>{explanationJobPollError}</p></> : <span>{ui("This saved job is still active. New explanation/check jobs are paused to prevent duplicate work.", "Задача ещё выполняется. Новый запуск недоступен, чтобы не дублировать работу.")}</span>}<Button view="outlined" disabled={busy} onClick={resumeExplanationJob}>{explanationJob.status === "succeeded" ? "Recover saved job result" : "Resume saved job"}</Button></div>}
          </>
        )}
        {error && <div className="error" role="alert">{error}</div>}
        {explanation && (
          <div className="evidence-explanation-result">
            <div className="evidence-explanation-summary"><strong>{ui("Explained model output", "Объясняемый выход модели")}: {explanation.prediction.toFixed(4)}</strong><span>{explanation.output_space}</span></div>
            <AttributionChart explanation={explanation} />
            <details className="evidence-advanced-details" data-testid="explanation-technical-details">
              <summary>{ui("Values and scientific details", "Значения и научные подробности")}</summary>
              <div className="evidence-result-grid">
                <section className="trace-card">
                  <strong>{ui("Explanation contract", "Контракт объяснения")}</strong>
                  <div><span>{ui("Category", "Категория")}</span><code>{explanation.epistemic_category}</code></div>
                  <div><span>{ui("Method", "Метод")}</span><code>{explanation.method}</code></div>
                  <div><span>{ui("Output space", "Шкала выхода")}</span><code>{explanation.output_space}</code></div>
                  {explanation.preprocessing_identity && <div><span>{ui("Preprocessing", "Подготовка данных")}</span><code>{explanation.preprocessing_identity.slice(0, 28)}…</code></div>}
                  {explanation.sample_identity && <div><span>{ui("Sample identity", "Пример данных")}</span><code>{explanation.sample_identity.slice(0, 28)}…</code></div>}
                  {explanation.base_value !== null && <div><span>{ui("Base value", "Базовый выход")}</span><code>{explanation.base_value.toFixed(6)}</code></div>}
                  {explanation.completeness_error !== null && <div><span>{ui("Completeness error", "Невязка объяснения")}</span><code>{explanation.completeness_error.toExponential(3)}</code></div>}
                  <p>{explanation.scientific_note}</p>
                </section>
                <section className="trace-card">
                  <strong>{ui("All feature values", "Все значения признаков")}</strong>
                  {[...explanation.attributions].sort((a, b) => Math.abs(b.attribution) - Math.abs(a.attribution)).map((item) => (
                    <div key={item.feature}>
                      <span>{item.feature}: {item.observed_value.toFixed(4)} → ref {item.reference_value.toFixed(4)}</span>
                      <code>{formatAttribution(item.attribution)}</code>
                    </div>
                  ))}
                </section>
                <section className="trace-card evidence-limitations">
                  <strong>{ui("Assumptions / limits", "Допущения и ограничения")}</strong>
                  {explanation.assumptions.map((item) => <p key={item}>{ui("Assumption", "Допущение")} · {item}</p>)}
                  {explanation.limitations.map((item) => <p key={item}>{ui("Limit", "Ограничение")} · {item}</p>)}
                </section>
              </div>
            </details>
          </div>
        )}
      </section>

      {explanation && (
        <section className="evidence-section">
          <div className="feature-toolbar compact-toolbar">
            <div><span className="eyebrow">{ui("CHECK EXPLANATION", "ПРОВЕРКА ОБЪЯСНЕНИЯ")}</span><h3>{ui("Available technical checks", "Проверки сохранённого объяснения")}</h3></div>
            <details open={uiLanguage === "en"}><summary>{ui("Execution details", "Технические настройки")}</summary>            <label className="field-label">{ui("Validator", "Проверяющий модуль")}<select aria-label={ui("Explanation validator", "Модуль проверки объяснения")} value={validatorKey} disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !runtimeValidators.length} onChange={(event) => setValidatorKey(event.target.value)}>{runtimeValidators.map((validator) => <option key={validator.identity.key} value={validator.identity.key}>{validator.identity.key} · {validator.identity.provider}</option>)}</select></label></details>
            <Button view="outlined" disabled={busy || project.read_only || runtimeCatalogHydrationStatus !== "available" || !runtimeValidators.length || !executionBackends.length || explanationJobHydrationStatus === "loading" || explanationJobHydrationStatus === "error" || !!explanationJobPollError || !!explanationJob && ["queued", "running"].includes(explanationJob.status)} onClick={check} data-ruflex-action="explanation.check">{ui("Run explanation checks", "Проверить объяснение")}</Button>
          </div>
          {explanationCheck && explanationCheck.explanation_id !== explanation.explanation_id ? <div className="error" role="alert" data-testid="explanation-check-mismatch"><strong>{ui("Saved check belongs to a different explanation.", "Сохранённая проверка относится к другому объяснению.")}</strong><p>{ui("The persisted ExplanationCheck is not displayed as validation of the currently selected explanation.", "Эта проверка не подтверждает выбранное сейчас объяснение.")}</p></div> : explanationCheck ? (
            <div className="trace-card">
              <div className="evidence-check-header"><strong>{ui("Check result", "Результат проверки")}</strong><span data-testid="explanation-check-status" data-status={explanationCheck.status}><StatusBadge tone={statusTone(explanationCheck.status)}>{explanationCheck.status === "PASSED_AVAILABLE_CHECKS" ? ui("Available checks passed", "Доступные проверки пройдены") : explanationCheck.status === "WARNING" ? ui("Checks have warnings", "Есть замечания") : ui("Checks failed", "Проверки не пройдены")}</StatusBadge></span></div>
              <p className="property-description">{ui("Technical checks assess the saved explanation; they do not establish causality.", "Технические проверки оценивают сохранённое объяснение, но не доказывают причинность.")}</p>
              <details className="evidence-advanced-details" data-testid="explanation-check-details"><summary>{ui("Show individual checks", "Показать отдельные проверки")}</summary>
                {validatorPlugins.filter((plugin) => explanationCheck.checks.some((item) => item.validator_key === plugin.key)).map((plugin) => <p className="property-description" data-testid="validator-plugin" key={plugin.key}>Validator · {plugin.key} v{plugin.version} · {Object.entries(plugin.capabilities).filter(([, available]) => available).map(([key]) => key.replaceAll("_", " ")).join(", ")}</p>)}
                {explanationCheck.checks.map((item) => (
                  <div className="evidence-check-detail" key={item.name}>
                    <span><strong>{item.category.replaceAll("_", " ")}</strong> · {item.name} · {item.detail}</span>
                    <StatusBadge tone={statusTone(item.status)}>{item.status}</StatusBadge>
                  </div>
                ))}
                <p>{explanationCheck.scientific_note}</p>
                <small className="mono">{explanationCheck.status}</small>
              </details>
            </div>
          ) : explanationCheckHydrationStatus === "error" ? <div className="error" role="alert" data-testid="explanation-check-hydration-error"><strong>{ui("Saved explanation check could not be verified.", "Не удалось проверить сохранённый результат.")}</strong><p>{explanationCheckHydrationError}</p>{onRetryExplanationCheck && <Button view="outlined" onClick={onRetryExplanationCheck}>{ui("Retry explanation check", "Повторить проверку")}</Button>}</div> : explanationCheckHydrationStatus === "loading" ? <p role="status">{ui("Loading saved explanation check…", "Загрузка проверки…")}</p> : <p className="property-description">{ui("Not checked yet. A generated explanation is not automatically validated.", "Проверка ещё не запускалась. Создание объяснения не подтверждает его корректность.")}</p>}
        </section>
      )}
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("BEHAVIOR SPECS", "ТРЕБОВАНИЯ К ПОВЕДЕНИЮ")}</span><h3>{ui("Revision-bound engineering checks", "Проверки конкретной версии модели")}</h3><p>{ui("Each execution binds to the persisted model artifact; PASS/FAIL is evidence, not a trust score.", "Задайте ожидаемый результат и проверьте выбранный пример.")}</p></div></div>
        {behaviorSpecResultStatus === "loading" && <p role="status">{ui("Loading saved BehaviorSpec result and its exact specification…", "Загрузка сохранённой проверки…")}</p>}
        {behaviorSpecResultStatus === "none" && <p className="property-description" data-testid="behavior-result-empty">{ui("No saved BehaviorSpec result is available for this project.", "Проверка требований ещё не выполнялась.")}</p>}
        {behaviorSpecResultStatus === "error" && <div className="error" role="alert"><strong>{ui("Saved BehaviorSpec evidence could not be verified.", "Не удалось проверить сохранённое требование.")}</strong><p>{behaviorSpecResultError}</p>{onRetryBehaviorSpecResult && <Button view="outlined" onClick={onRetryBehaviorSpecResult}>{ui("Retry saved BehaviorSpec", "Повторить загрузку проверки")}</Button>}</div>}
        {(modelContextStatus === "idle" || modelContextStatus === "loading") && <p role="status" data-testid="behavior-model-context-loading">{ui("Checking saved FIS and training-run context before creating a requirement…", "Загрузка модели для создания требования…")}</p>}
        {modelContextStatus === "error" && <div className="error" role="alert" data-testid="behavior-model-context-error"><strong>{ui("Saved model context could not be verified; BehaviorSpec creation is paused.", "Не удалось проверить модель. Создание требования временно недоступно.")}</strong><p>{modelContextError ?? "The project is not assumed to have no model after a failed read."}</p>{onRetryModelContext && <Button view="outlined" onClick={onRetryModelContext}>{ui("Retry saved model context", "Повторить загрузку модели")}</Button>}</div>}
        {modelContextStatus === "loaded" && !run && !fis && <EmptyState title="No model revision selected">{ui("Select a persisted training run or save a FIS revision to create a BehaviorSpec. Saved requirements remain inspectable below.", "Сначала выберите обученную модель или сохраните нечёткую модель. Ранее созданные требования доступны ниже.")}</EmptyState>}
        {modelContextStatus === "loaded" && (run || fis) && <>
          <label className="field-label">{ui("Model source", "Модель для проверки")}<select aria-label={ui("Behavior model source", "Модель для проверки")} value={behaviorSource} disabled={busy || !!behaviorSpecCreationRecoveryRequest} onChange={(event) => setBehaviorSource(event.target.value as "run" | "fis")}><option value="run" disabled={!run}>{ui("Training run", "Обученная модель")}</option><option value="fis" disabled={!fis}>{ui("Saved FIS revision", "Сохранённая нечёткая модель")}</option></select></label>
          {behaviorSource === "fis" && fis && <><p className="property-description">FIS {fis.name} · exact saved semantic revision {fis.semantic_hash ?? "not saved"}</p>{!fis.semantic_hash && <p className="error" role="alert">{ui("Save this FIS revision before creating a BehaviorSpec.", "Сохраните нечёткую модель перед созданием требования.")}</p>}<div className="evidence-sample-grid">{fis.inputs.map((input) => <label className="field-label" key={`behavior-fis-${input.name}`}>Primary {input.name}<input aria-label={`Behavior input ${input.name}`} type="number" min={input.minimum} max={input.maximum} value={fisSample[input.name] ?? ""} disabled={busy || !!behaviorSpecCreationRecoveryRequest} onChange={(event) => setFisSample((current) => ({ ...current, [input.name]: event.target.value }))} /></label>)}</div></>}
          <fieldset disabled={busy || !!behaviorSpecCreationRecoveryRequest} style={{ border: 0, margin: 0, padding: 0 }}>
          <div className="contract-grid"><label className="field-label">{ui("Name", "Название")}<TextInput aria-label={ui("Behavior spec name", "Название требования")} value={behaviorName} onUpdate={setBehaviorName} /></label><label className="field-label">{ui("Type", "Тип проверки")}<select aria-label={ui("Behavior spec type", "Тип проверки")} value={behaviorKind} onChange={(event) => setBehaviorKind(event.target.value as BehaviorSpec["kind"])}><option value="output_range">{ui("Output range", "Допустимый диапазон")}</option><option value="monotonic_pair">{ui("Monotonic pair", "Изменение в заданную сторону")}</option><option value="invariance_pair">{ui("Invariance pair", "Неизменность выхода")}</option><option value="symmetry_pair">{ui("Symmetry pair", "Симметрия")}</option><option value="bounded_perturbation">{ui("Bounded perturbation", "Ограниченное изменение")}</option><option value="categorical_invariance">{ui("Categorical invariance", "Неизменность при смене категории")}</option><option value="forbidden_region">{ui("Forbidden output region", "Запрещённый диапазон")}</option><option value="required_order">{ui("Required order", "Порядок значений")}</option><option value="domain_constraint">{ui("Domain constraint", "Предметное ограничение")}</option><option value="regression_case">{ui("Expert regression case", "Экспертный контрольный пример")}</option><option value="batch_regression_suite">{ui("Two-case regression suite", "Два контрольных примера")}</option></select></label>{(["monotonic_pair", "required_order"] as string[]).includes(behaviorKind) && <label className="field-label">{ui("Direction", "Направление")}<select aria-label={ui("Monotonic direction", "Направление изменения")} value={direction} onChange={(event) => setDirection(event.target.value as typeof direction)}><option value="nondecreasing">{ui("Nondecreasing", "Не убывает")}</option><option value="nonincreasing">{ui("Nonincreasing", "Не возрастает")}</option></select></label>}{behaviorKind === "bounded_perturbation" && <label className="field-label">{ui("Maximum delta", "Допустимое изменение")}<input aria-label={ui("Behavior maximum delta", "Допустимое изменение выхода")} type="number" value={maximumDelta} onChange={(event) => setMaximumDelta(event.target.value)} /></label>}{!(["monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order"] as string[]).includes(behaviorKind) && <><label className="field-label">{ui("Minimum", "Минимум")}<input aria-label={ui("Behavior minimum", "Минимум выхода")} type="number" value={minimum} onChange={(event) => setMinimum(event.target.value)} /></label><label className="field-label">{ui("Maximum", "Максимум")}<input aria-label={ui("Behavior maximum", "Максимум выхода")} type="number" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></label></>}</div>
          {(["monotonic_pair", "invariance_pair", "symmetry_pair", "bounded_perturbation", "categorical_invariance", "required_order", "batch_regression_suite"] as string[]).includes(behaviorKind) && <><p className="field-help">{ui("Define both cases explicitly. RuFLEX does not infer a pairwise requirement from a single sample.", "Укажите оба сравниваемых примера. Одного примера недостаточно.")}</p><div className="evidence-sample-grid">{(behaviorSource === "fis" ? fis?.inputs.map((input) => input.name) ?? [] : run?.feature_columns ?? []).map((feature) => <label className="field-label" key={`comparison-${feature}`}>Comparison {feature}<input aria-label={`Behavior comparison ${feature}`} type="number" value={behaviorSource === "fis" ? fisComparisonSample[feature] ?? "" : comparisonSample[feature] ?? ""} disabled={busy || !!behaviorSpecCreationRecoveryRequest} onChange={(event) => behaviorSource === "fis" ? setFisComparisonSample((current) => ({ ...current, [feature]: event.target.value })) : setComparisonSample((current) => ({ ...current, [feature]: event.target.value }))} /></label>)}</div></>}
          </fieldset>
          {behaviorSpecCreationRecoveryRequest && <div className="error" role="alert" data-testid="behavior-spec-create-recovery"><strong>{ui("BehaviorSpec creation outcome is uncertain; resolve the exact model revision and definition before changing it.", "Не удалось подтвердить сохранение требования. Сначала найдите его результат.")}</strong><p>{behaviorSpecCreationRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverBehaviorSpecCreation}>{ui("Retry saved requirement lookup", "Найти сохранённое требование")}</Button>{behaviorSpecCreationNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyRestartBehaviorSpecCreation}>{ui("Create this requirement explicitly", "Повторить сохранение требования")}</Button>}</div>}
          <Button view="action" disabled={busy || project.read_only || (behaviorSource === "fis" ? !fis?.semantic_hash : !run) || !!behaviorExecutionRecoveryError || !!behaviorSpecCreationRecoveryRequest} onClick={createAndRunBehavior} data-ruflex-action="behavior.run">{busy ? ui("Running…", "Проверка…") : ui("Create and run BehaviorSpec", "Сохранить и проверить требование")}</Button>
          {behaviorExecutionRecoveryError && <div className="error" role="alert" data-testid="behavior-run-recovery"><strong>{ui("The BehaviorSpec is already saved; retry its result by the same identity.", "Требование уже сохранено. Повторите получение его результата.")}</strong><p>{behaviorExecutionRecoveryError}</p><Button view="outlined" disabled={busy} onClick={resumeBehaviorSpecExecution}>{ui("Retry saved BehaviorSpec", "Повторить загрузку проверки")}</Button></div>}
        </>}
          {behaviorSpec && <details open={uiLanguage === "en"}><summary>{ui("Saved requirement", "Сохранённое требование")}</summary><div className="trace-card" data-testid="behavior-spec"><div className="evidence-check-header"><strong>{readableBehaviorName(behaviorSpec.name)}</strong><StatusBadge tone="info">{behaviorKindLabel(behaviorSpec.kind)}</StatusBadge></div><p>{behaviorSpec.rationale === "Persisted engineering behavior requirement." ? ui(behaviorSpec.rationale, "Проверка заданного требования на выбранном примере.") : behaviorSpec.rationale}</p><details><summary>{ui("Model reference", "Сведения о версии модели")}</summary><small>{behaviorSpec.run_id ? `Run-bound requirement · ${behaviorSpec.run_id.slice(0, 12)}` : `FIS-bound requirement · ${behaviorSpec.fis_semantic_hash?.slice(0, 12)}`}</small></details></div></details>}
          {behaviorResult && <div className="trace-card" data-testid="behavior-result"><div className="evidence-check-header"><strong>{behaviorSpec ? readableBehaviorName(behaviorSpec.name) : ui("Persisted BehaviorSpec", "Сохранённое требование")}</strong><StatusBadge tone={behaviorResult.status === "PASS" ? "success" : "danger"}>{behaviorResult.status}</StatusBadge></div>{uiLanguage === "en" ? <p>{behaviorResult.detail}</p> : behaviorSpec ? <BehaviorResultSummary spec={behaviorSpec} result={behaviorResult} /> : <p>Откройте связанное требование для просмотра результата.</p>}<details><summary>{ui("Model reference", "Сведения о версии модели")}</summary><small>{behaviorResult.run_id ? `Run ${behaviorResult.run_id.slice(0, 12)} · artifact ${behaviorResult.model_artifact_sha256?.slice(0, 12)}` : `FIS revision ${behaviorResult.fis_semantic_hash?.slice(0, 12)}`}</small></details></div>}
          {behaviorSpec && behaviorResult && <BehaviorCounterexample spec={behaviorSpec} result={behaviorResult} />}
          {behaviorSpec && behaviorResult && <BehaviorExactTrace spec={behaviorSpec} result={behaviorResult} />}
          <details open={uiLanguage === "en"}><summary>{ui("Compare model revisions", "Сравнить версии модели")}</summary>          {lineageBehaviorComparison && <div className="trace-card" data-testid="behavior-revision-comparison"><div className="evidence-check-header"><strong>{ui("Persisted revision comparison", "Сравнение версий модели")}</strong><StatusBadge tone={lineageBehaviorComparison.regression_detected ? "danger" : "info"}>{lineageBehaviorComparison.transition.replaceAll("_", " ")}</StatusBadge></div><p>{lineageBehaviorComparison.regression_detected ? "A PASS-to-FAIL transition was retained as regression evidence." : "No PASS-to-FAIL regression was observed in this transition."}</p><small>Baseline {lineageBehaviorComparison.baseline_result_id.slice(0, 12)} · candidate {lineageBehaviorComparison.candidate_result_id.slice(0, 12)} · {lineageBehaviorComparison.requirement_identity.slice(0, 16)}</small><p>{lineageBehaviorComparison.scientific_note}</p></div>}
          <section className="trace-card"><strong>{ui("Revision transition", "Изменение результата")}</strong><p>{ui("Compare two executions of the exact same persisted behavior requirement across model or FIS revisions. A PASS → FAIL transition is retained as regression evidence.", "Сравните одно и то же требование для двух версий модели. Переход от выполнения к нарушению будет показан как ухудшение.")}</p>{behaviorResultsHydrationStatus === "loading" && <p role="status" data-testid="behavior-results-loading">{ui("Loading saved BehaviorSpec results…", "Загрузка результатов требований…")}</p>}{behaviorResultsHydrationStatus === "error" && <div className="error" role="alert" data-testid="behavior-results-hydration-error"><strong>{ui("Saved BehaviorSpec results could not be verified; comparison is paused.", "Не удалось проверить результаты. Сравнение временно недоступно.")}</strong><p>{behaviorResultsHydrationError}</p><Button view="outlined" onClick={() => setBehaviorResultsHydrationReload((current) => current + 1)}>{ui("Retry BehaviorSpec results", "Повторить загрузку результатов")}</Button></div>}<div className="training-config-grid"><label className="field-label">{ui("Baseline result", "Исходный результат")}<select aria-label="Behavior baseline result" disabled={!!behaviorComparisonRecoveryPair} value={baselineBehaviorResultId} onChange={(event) => setBaselineBehaviorResultId(event.target.value)}><option value="">{ui("Choose result", "Выберите результат")}</option>{behaviorResults.map((item) => <option key={item.result_id} value={item.result_id}>{item.result_id.slice(0, 8)} · {item.status}</option>)}</select></label><label className="field-label">{ui("Candidate result", "Новый результат")}<select aria-label="Behavior candidate result" disabled={!!behaviorComparisonRecoveryPair} value={candidateBehaviorResultId} onChange={(event) => setCandidateBehaviorResultId(event.target.value)}><option value="">{ui("Choose result", "Выберите результат")}</option>{behaviorResults.map((item) => <option key={item.result_id} value={item.result_id}>{item.result_id.slice(0, 8)} · {item.status}</option>)}</select></label></div><Button view="outlined" disabled={busy || !!behaviorComparisonRecoveryPair || project.read_only || behaviorResultsHydrationStatus !== "available" || behaviorComparisonHydrationStatus === "loading" || behaviorComparisonHydrationStatus === "error" || !baselineBehaviorResultId || !candidateBehaviorResultId || baselineBehaviorResultId === candidateBehaviorResultId} onClick={compareBehaviorRevisions} data-ruflex-action="behavior.revision.compare">{ui("Compare revisions", "Сравнить версии")}</Button>{behaviorComparisonRecoveryPair && <div className="error" role="alert" data-testid="behavior-comparison-recovery"><strong>{ui("Comparison outcome is uncertain; resolve this exact result pair before changing it.", "Результат сравнения не подтверждён. Сначала найдите сохранённое сравнение.")}</strong><p>{behaviorComparisonRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverBehaviorRevisionComparison}>{ui("Retry saved comparison lookup", "Найти сохранённое сравнение")}</Button>{behaviorComparisonRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyRestartBehaviorRevisionComparison}>{ui("Repeat comparison explicitly", "Повторить сравнение")}</Button>}</div>}{behaviorComparisonHydrationStatus === "loading" && <p role="status" data-testid="behavior-comparison-loading">{ui("Loading saved revision comparison…", "Загрузка сравнения версий…")}</p>}{behaviorComparisonHydrationStatus === "none" && <p className="property-description" data-testid="behavior-comparison-empty">{ui("No saved revision comparison is available.", "Версии ещё не сравнивали.")}</p>}{behaviorComparisonHydrationStatus === "error" && <div className="error" role="alert" data-testid="behavior-comparison-hydration-error"><strong>{ui("Saved revision comparison could not be verified; creating another comparison is paused.", "Не удалось проверить сравнение версий. Новое сравнение пока недоступно.")}</strong><p>{behaviorComparisonHydrationError}</p><Button view="outlined" onClick={() => setBehaviorComparisonHydrationReload((current) => current + 1)}>{ui("Retry saved revision comparison", "Повторить загрузку сравнения")}</Button></div>}{behaviorComparison && <p data-testid="behavior-revision-comparison"><strong>{behaviorComparison.transition.replaceAll("_", " ")}</strong> · {behaviorComparison.regression_detected ? "regression retained as evidence" : "no PASS-to-FAIL regression in this transition"}</p>}</section></details>
      </section>
      <details className="evidence-advanced-details" open={uiLanguage === "en"}><summary>{ui("Additional evidence tools", "Дополнительно: сводка проверок, экспорт и сравнение запусков")}</summary>      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("CONDITION MONITORING DEMO", "ПРИМЕР ПРОВЕРКИ ТЕЛЕМЕТРИИ")}</span><h3>Telemetry decision support with review and scope safeguards</h3><p>Telemetry → frozen class/selective policy → scope → explanation check → AssuranceCase → VerificationBundle → ACCEPT / REVIEW / OUT-OF-SCOPE. This is not targeting or actuator control.</p></div><Button view="action" disabled={busy || project.read_only || !run || !selectivePolicy || !!demoRecoveryRequest || !["none", "available"].includes(demoHydrationStatus) || generalizationHydrationStatus === "loading" || generalizationHydrationStatus === "error" || generalizationHydrationStatus === "idle"} onClick={runConditionDemo} data-ruflex-action="condition_demo.run">Run telemetry demonstration</Button></div>{demoRecoveryRequest && <div className="error" role="alert" data-testid="condition-demo-recovery"><strong>Demonstration request outcome is uncertain; resolve its exact saved inputs and policy first.</strong><p>{demoRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverConditionDemo}>Retry saved demo lookup</Button>{demoRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyRestartConditionDemo}>Rerun saved demo explicitly</Button>}</div>}{demoHydrationStatus === "loading" && <p role="status" data-testid="condition-demo-loading">Loading saved condition-monitoring evidence…</p>}{demoHydrationStatus === "none" && <p className="property-description" data-testid="condition-demo-empty">No saved condition-monitoring result is available.</p>}{demoHydrationStatus === "error" && <div className="error" role="alert" data-testid="condition-demo-hydration-error"><strong>Saved condition-monitoring evidence could not be verified; another demonstration is paused.</strong><p>{demoHydrationError}</p><Button view="outlined" onClick={() => setDemoHydrationReload((current) => current + 1)}>Retry condition-monitoring evidence</Button></div>}{generalizationHydrationStatus === "loading" && <p role="status">Resolving the saved GeneralizationContract before scope-aware review…</p>}{generalizationHydrationStatus === "none" && <p className="property-description">No GeneralizationContract is saved; this demonstration will report scope as undeclared.</p>}{generalizationHydrationStatus === "error" && <div className="error" role="alert" data-testid="evidence-generalization-hydration-error"><strong>Saved GeneralizationContract could not be verified; the scope-aware demonstration is paused.</strong><p>{generalizationHydrationError}</p>{onRetryGeneralization && <Button view="outlined" onClick={onRetryGeneralization}>Retry GeneralizationContract</Button>}</div>}{!selectivePolicy && <p className="property-description">A validation-derived selective policy is required before this demonstration can make an ACCEPT/REVIEW decision.</p>}{demo && <div className="trace-card" data-testid="condition-monitoring-demo"><StatusBadge tone={demo.decision === "ACCEPT" ? "success" : demo.decision === "OUT_OF_SCOPE" ? "danger" : "warning"}>{demo.decision}</StatusBadge><p>Class {demo.predicted_class} · probability {demo.probability.toFixed(4)} · confidence {demo.confidence.toFixed(4)} · scope {demo.scope_disposition}</p><small className="mono">Explanation {demo.explanation_id?.slice(0, 12)} · check {demo.explanation_check_id?.slice(0, 12)} · AssuranceCase {demo.assurance_id?.slice(0, 12)} · VerificationBundle {demo.verification_bundle_sha256?.slice(0, 12)}</small><p>{demo.explanation_note}</p><small>{demo.safety_note}</small></div>}</section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("ASSURANCE CASE", "СВОДКА ПРОВЕРОК")}</span><h3>{ui("Independent evidence gates and qualified claims", "Сводка выполненных проверок")}</h3><p>{ui("No universal trust score is produced.", "Это сводка результатов, а не универсальный рейтинг надёжности.")}</p></div><Button view="action" disabled={busy || project.read_only || evidenceOperationPending} onClick={buildAssurance} data-ruflex-action="assurance.create">{busy ? "Building…" : "Build AssuranceCase"}</Button></div>{evidenceOperationPending && <div className={evidenceOperationPollError ? "error" : "property-description"} role={evidenceOperationPollError ? "alert" : "status"} data-testid="evidence-operation-resume"><strong>{evidenceOperationJob?.kind.replaceAll("_", " ")} · job {evidenceOperationJob?.job_id.slice(0, 12)}</strong>{evidenceOperationPollError ? <p>{evidenceOperationPollError}</p> : <p>This persisted evidence operation is still active; duplicate evidence jobs are paused.</p>}<Button view="outlined" disabled={busy} onClick={resumeEvidenceOperation}>Resume saved evidence job</Button></div>}{assuranceHydrationStatus === "loading" && <p role="status">Loading saved AssuranceCase…</p>}{assuranceHydrationStatus === "none" && !assurance && <p className="property-description" data-testid="assurance-empty">No saved AssuranceCase is available for this project.</p>}{assuranceHydrationStatus === "error" && <div className="error" role="alert"><strong>Saved AssuranceCase could not be verified.</strong><p>{assuranceHydrationError}</p>{onRetryAssurance && <Button view="outlined" onClick={onRetryAssurance}>Retry AssuranceCase</Button>}</div>}{assurance && <div className="trace-card" data-testid="assurance-case"><p>{assurance.scientific_note}</p><div className="data-table-wrap"><table className="data-table"><thead><tr><th>{ui("gate", "Проверка")}</th><th>{ui("status", "Результат")}</th><th>{ui("evidence / risk", "Основание и ограничения")}</th></tr></thead><tbody>{assurance.gates.map((gate) => <tr key={gate.key}><td>{gate.key.replaceAll("_", " ")}</td><td><StatusBadge tone={gate.status === "PASS" ? "success" : gate.status === "FAIL" ? "danger" : "warning"}>{gate.status}</StatusBadge></td><td>{gate.evidence.join(", ") || gate.risk || "—"}</td></tr>)}</tbody></table></div>{assurance.claims.length > 0 && <div className="assurance-claims"><strong>{ui("Claim graph", "Выводы и основания")}</strong>{assurance.claims.map((claim) => <div className="property-description" key={claim.claim_id}><StatusBadge tone={claim.status === "SUPPORTED" ? "success" : claim.status === "UNSUPPORTED" ? "danger" : "warning"}>{claim.status}</StatusBadge><p>{claim.statement}</p><small>Evidence: {claim.evidence_ids.join(", ")}</small>{claim.limitations.map((limitation) => <small key={limitation}>Limitation: {limitation}</small>)}</div>)}</div>}{assurance.unresolved_risks.map((risk) => <p className="property-description" key={risk}>Unresolved risk · {risk}</p>)}</div>}</section>
      <section className="evidence-section"><div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("VERIFICATION BUNDLE", "ЭКСПОРТ РЕЗУЛЬТАТОВ")}</span><h3>{ui("Inspection-first evidence export", "Экспорт сохранённых результатов")}</h3><p>{ui("Exports declarative evidence and checksums; it excludes executable code, pickle/joblib, raw datasets, credentials, caches and node_modules.", "В архив попадут результаты и сведения об их происхождении. Исполняемый код, исходные данные и пароли не включаются.")}</p></div><Button view="outlined" disabled={busy || project.read_only || !assurance || evidenceOperationPending} onClick={exportBundle} data-ruflex-action="bundle.export">{ui("Export and validate bundle", "Экспортировать и проверить архив")}</Button></div>{verificationBundleRecord && <div className="trace-card" data-testid="verification-bundle-record"><div className="evidence-check-header"><strong>{ui("Persisted VerificationBundle", "Сохранённый архив результатов")}</strong><StatusBadge tone="info">{ui("inspection first", "для просмотра")}</StatusBadge></div><p>{verificationBundleRecord.entry_count} declarative entries · SHA-256 {verificationBundleRecord.sha256}</p><small>Manifest {verificationBundleRecord.manifest_sha256} · linked AssuranceCase {verificationBundleRecord.assurance_id}</small><div><Button view="outlined" disabled={bundleDownloadPending} onClick={downloadBundle} data-ruflex-action="bundle.download">{bundleDownloadPending ? "Checking bundle…" : "Download verified ZIP"}</Button></div>{bundleDownloadError && <p className="error" role="alert">Download unavailable: {bundleDownloadError}</p>}</div>}{bundle && <div className="trace-card" data-testid="verification-bundle"><p>{bundle.entry_count} inspection entries · SHA-256 {bundle.sha256}</p><small>{bundle.path}</small>{bundleValidation && <><div className="evidence-check-header"><strong>{ui("Portable validation", "Проверка архива")}</strong><StatusBadge tone={bundleValidation.status === "PASS" ? "success" : "danger"}>{bundleValidation.status}</StatusBadge></div><p>{bundleValidation.status === "PASS" ? `${bundleValidation.checked_entries} checksummed entries validated after export.` : bundleValidation.errors.join(" ")}</p>{bundleValidation.warnings.map((warning) => <p className="property-description" key={warning}>{warning}</p>)}</>}</div>}</section>
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("EXHAUSTIVE LAB", "ПРОВЕРКА КОНЕЧНЫХ СОСТОЯНИЙ")}</span><h3>{ui("Finite structure and declared discrete-grid evidence", "Проверка конечного набора состояний")}</h3><p>{ui("Exactness applies only to the finite tree structure or the explicitly declared FIS grid—not to arbitrary continuous models.", "Перебираются только ветви дерева или заданная сетка нечёткой модели, не все возможные входы.")}</p></div></div>
        {exhaustiveHydrationStatus === "loading" && <p role="status">Loading saved exhaustive evidence…</p>}
        {exhaustiveHydrationStatus === "none" && <p className="property-description" data-testid="exhaustive-empty">No saved exhaustive evidence is available.</p>}
        {exhaustiveHydrationStatus === "error" && <div className="error" role="alert" data-testid="exhaustive-hydration-error"><strong>Saved exhaustive evidence could not be verified.</strong><p>{exhaustiveHydrationError}</p>{onRetryExhaustive && <Button view="outlined" onClick={onRetryExhaustive}>Retry exhaustive evidence</Button>}</div>}
        {exhaustiveRecoveryRequest && <div className="error" role="alert" data-testid="exhaustive-recovery"><strong>Exhaustive request outcome is uncertain; resolve the saved request before changing it.</strong><p>{exhaustiveRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverExhaustive}>Retry saved result lookup</Button>{exhaustiveRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyRestartExhaustive}>Rerun saved request explicitly</Button>}</div>}
        <div className="toolbar-actions">{run?.model_kind === "decision_tree" && <Button view="action" disabled={busy || project.read_only || !!exhaustiveRecoveryRequest} onClick={() => runExhaustive("decision_tree_structure")} data-ruflex-action="exhaustive.tree.run">Enumerate exact Decision Tree paths</Button>}{evaluation && <><label className="field-label">Grid points/input<input aria-label="Exhaustive grid points" type="number" min="2" max="9" value={gridPoints} disabled={!!exhaustiveRecoveryRequest} onChange={(event) => setGridPoints(event.target.value)} /></label><Button view="outlined" disabled={busy || project.read_only || !!exhaustiveRecoveryRequest} onClick={() => runExhaustive("fis_discrete_grid")} data-ruflex-action="exhaustive.fis.run">Evaluate declared FIS grid</Button></>}</div>
        {exhaustive && <div className="trace-card" data-testid="exhaustive-result"><StatusBadge tone="info">{exhaustive.exactness_label}</StatusBadge><p>{exhaustive.scientific_note}</p><p>{exhaustive.state_count} enumerated states (preflight estimate {exhaustive.state_estimate}, limit {exhaustive.max_states}) · uncovered {exhaustive.uncovered_states.length} · dead rules on declared grid {exhaustive.dead_rules.length} · overlap states {exhaustive.conflict_states.length}</p>{exhaustive.kind === "decision_tree_structure" && <div className="data-table-wrap"><table className="data-table"><thead><tr><th>leaf</th><th>constraints</th></tr></thead><tbody>{exhaustive.paths.slice(0, 20).map((item, index) => <tr key={index}><td>{String(item.leaf_id)}</td><td>{Array.isArray(item.constraints) ? item.constraints.join("; ") : "—"}</td></tr>)}</tbody></table></div>}{exhaustive.uncovered_states.length > 0 && <p className="property-description">Uncovered/undefined declared states are retained as evidence; they are not silently filled.</p>}</div>}
      </section>
      <section className="evidence-section">
        <div className="feature-toolbar compact-toolbar"><div><span className="eyebrow">{ui("CROSS-RUN EXPLANATION REPRODUCIBILITY", "СРАВНЕНИЕ ОБЪЯСНЕНИЙ")}</span><h3>{ui("Compare compatible frozen explanation evidence", "Сравнение сохранённых объяснений")}</h3><p>{ui("Prediction reproducibility and post-hoc explanation reproducibility are reported separately.", "Совпадение прогнозов и совпадение объяснений оцениваются отдельно.")}</p></div></div>
        {reproducibilityHydrationStatus === "loading" && <p role="status">Loading saved reproducibility analysis…</p>}
        {reproducibilityHydrationStatus === "none" && <p className="property-description" data-testid="reproducibility-empty">No saved cross-run reproducibility analysis is available.</p>}
        {reproducibilityHydrationStatus === "error" && <div className="error" role="alert" data-testid="reproducibility-hydration-error"><strong>Saved reproducibility analysis could not be verified.</strong><p>{reproducibilityHydrationError}</p>{onRetryReproducibility && <Button view="outlined" onClick={onRetryReproducibility}>Retry reproducibility analysis</Button>}</div>}
        {persistedExplanationsHydrationStatus === "loading" && <p role="status" data-testid="persisted-explanations-loading">Loading saved explanations…</p>}
        {persistedExplanationsHydrationStatus === "error" && <div className="error" role="alert" data-testid="persisted-explanations-hydration-error"><strong>Saved explanations could not be verified; reproducibility comparison is paused.</strong><p>{persistedExplanationsHydrationError}</p><Button view="outlined" onClick={() => setPersistedExplanationsHydrationReload((current) => current + 1)}>Retry saved explanations</Button></div>}
        {reproducibilityRecoveryIds && <div className="error" role="alert" data-testid="reproducibility-recovery"><strong>Reproducibility request outcome is uncertain; resolve the same explanation set before changing it.</strong><p>{reproducibilityRecoveryError}</p><Button view="outlined" disabled={busy} onClick={recoverReproducibility}>{ui("Retry saved comparison lookup", "Найти сохранённое сравнение")}</Button>{reproducibilityRecoveryNotFound && <Button view="outlined" disabled={busy} onClick={explicitlyRestartReproducibility}>Start a new comparison explicitly</Button>}</div>}
        {persistedExplanationsHydrationStatus === "available" && (persistedExplanations.length < 4 ? <EmptyState title="Need persisted explanation cases">Generate the same explanation method for the same declared cases across at least two compatible runs.</EmptyState> : <><div className="comparison-choice">{persistedExplanations.map((item) => <label key={item.explanation_id}><input type="checkbox" disabled={!!reproducibilityRecoveryIds} checked={selectedExplanationIds.includes(item.explanation_id)} onChange={(event) => setSelectedExplanationIds((current) => event.target.checked ? [...current, item.explanation_id] : current.filter((id) => id !== item.explanation_id))} />{item.run_id.slice(0, 8)} · {item.method} · case {item.sample_identity?.slice(-8)}</label>)}</div><Button view="action" disabled={busy || project.read_only || !!reproducibilityRecoveryIds || selectedExplanationIds.length < 4} onClick={compareReproducibility} data-ruflex-action="explanation.reproducibility.compare">{busy ? "Comparing…" : "Compare explanation reproducibility"}</Button></>)}
        {reproducibility && <div className="trace-card" data-testid="reproducibility-result"><p><StatusBadge tone="info">PREDICTION AGREEMENT</StatusBadge> class {(reproducibility.prediction_agreement.class_agreement * 100).toFixed(1)}% · mean |Δ| {reproducibility.prediction_agreement.mean_absolute_difference.toFixed(5)}</p><p><StatusBadge tone="warning">EXPLANATION AGREEMENT</StatusBadge> Spearman {reproducibility.explanation_agreement.mean_spearman?.toFixed(3) ?? "N/A"} · sign {(reproducibility.explanation_agreement.mean_sign_agreement * 100).toFixed(1)}% · top-k {(reproducibility.explanation_agreement.mean_top_k_overlap * 100).toFixed(1)}%</p><div className="data-table-wrap"><table className="data-table"><thead><tr><th>runs</th><th>prediction Δ</th><th>Spearman</th><th>sign</th><th>top-k</th></tr></thead><tbody>{reproducibility.pairwise.map((item) => <tr key={`${item.left_run_id}-${item.right_run_id}`}><td>{item.left_run_id.slice(0, 8)} / {item.right_run_id.slice(0, 8)}</td><td>{item.prediction_mean_absolute_difference.toFixed(5)}</td><td>{item.explanation_spearman?.toFixed(3) ?? "N/A"}</td><td>{(item.explanation_sign_agreement * 100).toFixed(1)}%</td><td>{(item.top_k_overlap * 100).toFixed(1)}%</td></tr>)}</tbody></table></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>feature</th><th>mean attribution</th><th>variability σ</th><th>sign agreement</th></tr></thead><tbody>{reproducibility.per_feature_variability.map((item) => <tr key={item.feature}><td>{item.feature}</td><td>{item.mean_attribution.toFixed(5)}</td><td>{item.standard_deviation.toFixed(5)}</td><td>{(item.sign_agreement * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>{reproducibility.warnings.map((warning) => <p className="property-description" key={warning}>Warning · {warning}</p>)}</div>}
      </section>
      </details>    </section>
  );
}
