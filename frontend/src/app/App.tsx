import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "../shell/AppShell";
import {
  Button,
  EmptyState,
  StatusBadge,
  TextInput,
} from "../components/StudioPrimitives";
import { ChartSurface } from "../charts/ChartSurface";
import { chartFixtures } from "../charts/fixtureOptions";
import { FlowGrammar } from "../flow/FlowGrammar";
import { ProjectLineage } from "../flow/ProjectLineage";
import { analysisOverviewLabel, evidenceOverviewLabel, projectModelOverviewLabel, projectStudyNextStep, trainingStudyOverviewLabel } from "./projectOverview";
import {
  ArtifactRecord,
  ProductApiError,
  AnalysisEvaluation,
  AnalysisComparison,
  CalibrationTransform,
  DecisionThresholdPolicy,
  FinalTestEvaluation,
  ExplanationCheck,
  BehaviorSpec,
  BehaviorSpecResult,
  BehaviorRevisionComparison,
  SelectivePredictionPolicy,
  ExplanationReproducibilityAnalysis,
  ExhaustiveLabResult,
  AssuranceCase,
  VerificationBundle,
  ExplanationContract,
  ExpertCorrectionRevision,
  TreePathEvidence,
  DatasetConfirmation,
  DatasetProfile,
  DatasetState,
  FISEvaluation,
  FISSpec,
  GeneralizationResponse,
  LineageGraph,
  LineageNode,
  LeakageAuditReport,
  SplitContract,
  TransformPipelineContract,
  ProjectSummary,
  ProjectIntegrityReport,
  ScopeClassification,
  SliceAnalysis,
  TrainingRun,
  TrainingStudy,
  StudyStabilityAnalysis,
  StabilityGatePolicy,
  studioApi,
} from "../api";
import { StudioTheme } from "../design/tokens";
import { BuildWorkspace } from "../features/modelbuild/BuildWorkspace";
import { EvidenceWorkspace } from "../features/evidence/EvidenceWorkspace";
import { ExperimentWorkspace } from "../features/training/ExperimentWorkspace";
import { EvaluationWorkspace } from "../features/training/EvaluationWorkspace";
import { ProjectExplorer } from "../explorer/ProjectExplorer";

type Panels = "explorer" | "inspector" | "bottom";
const MAX_DATASET_UPLOAD_BYTES = 5_000_000;
const SYNTHETIC_PRACTICE_CSV = [
  "entity_id,temperature,torque,target",
  ...Array.from({ length: 80 }, (_, index) => {
    const temperature = 10 + index % 20;
    const torque = 20 + index * 7 % 30;
    return `practice-${String(index + 1).padStart(3, "0")},${temperature},${torque},${index % 20 >= 10 ? 1 : 0}`;
  }),
].join("\n") + "\n";
const SYNTHETIC_PRACTICE_SHA256 = "37b5f2a3872ec570bacd35d8e031bc8336c18db744989df332a58d827cc08399";
type DataGovernanceObject =
  | { kind: "split_contract"; value: SplitContract }
  | { kind: "transform_pipeline"; value: TransformPipelineContract }
  | { kind: "leakage_audit"; value: LeakageAuditReport };
const initialTheme =
  (localStorage.getItem("ruflex.theme") as StudioTheme | null) ?? "light";
const RECENT_PROJECTS_STORAGE_KEY = "ruflex.recent-projects.v1";
type RecentProject = { name: string; path: string };
type PendingDatasetWrite = {
  sessionId: string;
  sourceArtifactSha256: string;
  target: string;
  task: string;
  idColumns: string[];
  excludedColumns: string[];
  sourceFormat: "csv" | "xlsx";
  draftKind: "csv_text" | "file";
  draftRevision: number;
  datasetFingerprint?: string;
};

function loadRecentProjects(): RecentProject[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(RECENT_PROJECTS_STORAGE_KEY) ?? "[]");
    if (!Array.isArray(stored)) return [];
    return stored.filter((item): item is RecentProject =>
      Boolean(item) && typeof item === "object"
      && typeof item.name === "string" && item.name.trim().length > 0
      && typeof item.path === "string" && item.path.trim().length > 0,
    ).slice(0, 8);
  } catch {
    return [];
  }
}

async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function App() {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>(loadRecentProjects);
  const [recentProjectError, setRecentProjectError] = useState<string | null>(null);
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [readOnly, setReadOnly] = useState(false);
  const [status, setStatus] = useState("Connecting to backend…");
  const [backendStatus, setBackendStatus] = useState<"checking" | "available" | "unavailable">("checking");
  const [backendHealthError, setBackendHealthError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [projectFormError, setProjectFormError] = useState<string | null>(null);
  const [projectLifecycleOperation, setProjectLifecycleOperation] = useState<"create" | "open" | "recent" | null>(null);
  const [projectWriteOperation, setProjectWriteOperation] = useState<"save" | "description" | null>(null);
  const [theme, setTheme] = useState<StudioTheme>(initialTheme);
  const [active, setActive] = useState("PROJECT");
  const [collapsed, setCollapsed] = useState<Record<Panels, boolean>>({
    explorer: false,
    inspector: false,
    bottom: false,
  });
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [artifactsHydrationStatus, setArtifactsHydrationStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [artifactsHydrationError, setArtifactsHydrationError] = useState<string | null>(null);
  const [artifactsHydrationReload, setArtifactsHydrationReload] = useState(0);
  const [csvText, setCsvText] = useState(
    "entity_id,temperature,torque,target\na,10,20,0\nb,20,50,1\nc,30,80,1\n",
  );
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [dataset, setDataset] = useState<DatasetConfirmation | null>(null);
  const [datasetState, setDatasetState] = useState<DatasetState | null>(null);
  const [datasetStateStatus, setDatasetStateStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [datasetStateError, setDatasetStateError] = useState<string | null>(null);
  const [datasetStateReload, setDatasetStateReload] = useState(0);
  const [overviewContextStatus, setOverviewContextStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [overviewContextSessionId, setOverviewContextSessionId] = useState<string | null>(null);
  const [overviewContextError, setOverviewContextError] = useState<string | null>(null);
  const [overviewContextReload, setOverviewContextReload] = useState(0);
  const [pendingDatasetFile, setPendingDatasetFile] = useState<File | null>(null);
  const [pendingDatasetProfile, setPendingDatasetProfile] = useState<DatasetProfile | null>(null);
  const [inspectingDatasetFile, setInspectingDatasetFile] = useState(false);
  const [importingDatasetFile, setImportingDatasetFile] = useState(false);
  const [confirmingCsvDataset, setConfirmingCsvDataset] = useState(false);
  const [target, setTarget] = useState("target");
  const [task, setTask] = useState("binary_classification");
  const [idColumns, setIdColumns] = useState("");
  const [excludedColumns, setExcludedColumns] = useState("");
  const [intendedUse, setIntendedUse] = useState("New entities");
  const [noveltyAxis, setNoveltyAxis] = useState("entity");
  const [generalization, setGeneralization] =
    useState<GeneralizationResponse | null>(null);
  const [generalizationHydrationStatus, setGeneralizationHydrationStatus] =
    useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [generalizationHydrationError, setGeneralizationHydrationError] = useState<string | null>(null);
  const [generalizationHydrationReload, setGeneralizationHydrationReload] = useState(0);
  const [scopeField, setScopeField] = useState("");
  const [scopeCandidateValue, setScopeCandidateValue] = useState("");
  const [supportedScopeValues, setSupportedScopeValues] = useState("");
  const [forbiddenScopeValues, setForbiddenScopeValues] = useState("");
  const [unsupportedAction, setUnsupportedAction] = useState<"BLOCK" | "REVIEW">("BLOCK");
  const [scopeClassification, setScopeClassification] = useState<ScopeClassification | null>(null);
  const [fis, setFis] = useState<FISSpec | null>(null);
  const [fisEvaluation, setFisEvaluation] = useState<FISEvaluation | null>(
    null,
  );
  const [fisEvaluationStatus, setFisEvaluationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [fisEvaluationError, setFisEvaluationError] = useState<string | null>(null);
  const [fisEvaluationReload, setFisEvaluationReload] = useState(0);
  const [previousFisEvaluation, setPreviousFisEvaluation] =
    useState<FISEvaluation | null>(null);
  const [trainingRun, setTrainingRun] = useState<TrainingRun | null>(null);
  const [trainingRuns, setTrainingRuns] = useState<TrainingRun[]>([]);
  const [trainingRunsStatus, setTrainingRunsStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [trainingRunsError, setTrainingRunsError] = useState<string | null>(null);
  const [trainingRunsReload, setTrainingRunsReload] = useState(0);
  const [trainingStudy, setTrainingStudy] = useState<TrainingStudy | null>(null);
  const [trainingStudyStatus, setTrainingStudyStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [trainingStudyError, setTrainingStudyError] = useState<string | null>(null);
  const [trainingStudyReload, setTrainingStudyReload] = useState(0);
  const [stabilityAnalysis, setStabilityAnalysis] = useState<StudyStabilityAnalysis | null>(null);
  const [stabilityAnalysisHydrationStatus, setStabilityAnalysisHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [stabilityAnalysisHydrationError, setStabilityAnalysisHydrationError] = useState<string | null>(null);
  const [stabilityAnalysisHydrationReload, setStabilityAnalysisHydrationReload] = useState(0);
  const [stabilityGatePolicy, setStabilityGatePolicy] = useState<StabilityGatePolicy | null>(null);
  const [analysisEvaluation, setAnalysisEvaluation] = useState<AnalysisEvaluation | null>(null);
  const [analysisEvaluationStatus, setAnalysisEvaluationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [analysisEvaluationError, setAnalysisEvaluationError] = useState<string | null>(null);
  const [analysisEvaluationReload, setAnalysisEvaluationReload] = useState(0);
  const [validationPolicyEvidenceStatus, setValidationPolicyEvidenceStatus] = useState<"idle" | "loading" | "available" | "error">("idle");
  const [validationPolicyEvidenceError, setValidationPolicyEvidenceError] = useState<string | null>(null);
  const [validationPolicyEvidenceReload, setValidationPolicyEvidenceReload] = useState(0);
  const [analysisComparison, setAnalysisComparison] = useState<AnalysisComparison | null>(null);
  const [analysisComparisonHydrationStatus, setAnalysisComparisonHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [analysisComparisonHydrationError, setAnalysisComparisonHydrationError] = useState<string | null>(null);
  const [analysisComparisonHydrationReload, setAnalysisComparisonHydrationReload] = useState(0);
  const [calibrationTransform, setCalibrationTransform] = useState<CalibrationTransform | null>(null);
  const [decisionThreshold, setDecisionThreshold] = useState<DecisionThresholdPolicy | null>(null);
  const [finalTestEvaluation, setFinalTestEvaluation] = useState<FinalTestEvaluation | null>(null);
  const [finalTestEvidenceStatus, setFinalTestEvidenceStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [finalTestEvidenceError, setFinalTestEvidenceError] = useState<string | null>(null);
  const [finalTestEvidenceReload, setFinalTestEvidenceReload] = useState(0);
  const [sliceAnalysis, setSliceAnalysis] = useState<SliceAnalysis | null>(null);
  const [sliceAnalysisHydrationStatus, setSliceAnalysisHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [sliceAnalysisHydrationError, setSliceAnalysisHydrationError] = useState<string | null>(null);
  const [sliceAnalysisHydrationReload, setSliceAnalysisHydrationReload] = useState(0);
  const [treeEvidence, setTreeEvidence] = useState<TreePathEvidence | null>(null);
  const [treeEvidenceHydrationStatus, setTreeEvidenceHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [treeEvidenceHydrationError, setTreeEvidenceHydrationError] = useState<string | null>(null);
  const [treeEvidenceHydrationReload, setTreeEvidenceHydrationReload] = useState(0);
  const handleStabilityAnalysisChange = useCallback((analysis: StudyStabilityAnalysis | null) => {
    setStabilityAnalysis(analysis);
    setStabilityAnalysisHydrationStatus(analysis ? "available" : "none");
    setStabilityAnalysisHydrationError(null);
  }, []);
  const [explanation, setExplanation] = useState<ExplanationContract | null>(null);
  const [explanationHydrationStatus, setExplanationHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [explanationHydrationError, setExplanationHydrationError] = useState<string | null>(null);
  const [explanationHydrationReload, setExplanationHydrationReload] = useState(0);
  const [explanationCheck, setExplanationCheck] = useState<ExplanationCheck | null>(null);
  const [explanationCheckHydrationStatus, setExplanationCheckHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [explanationCheckHydrationError, setExplanationCheckHydrationError] = useState<string | null>(null);
  const [explanationCheckHydrationReload, setExplanationCheckHydrationReload] = useState(0);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorSpecResult | null>(null);
  const [behaviorSpec, setBehaviorSpec] = useState<BehaviorSpec | null>(null);
  const [behaviorSpecResultStatus, setBehaviorSpecResultStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [behaviorSpecResultError, setBehaviorSpecResultError] = useState<string | null>(null);
  const [behaviorSpecResultReload, setBehaviorSpecResultReload] = useState(0);
  const [lineageBehaviorComparison, setLineageBehaviorComparison] = useState<BehaviorRevisionComparison | null>(null);
  const [selectivePolicy, setSelectivePolicy] = useState<SelectivePredictionPolicy | null>(null);
  const [reproducibility, setReproducibility] = useState<ExplanationReproducibilityAnalysis | null>(null);
  const [reproducibilityHydrationStatus, setReproducibilityHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [reproducibilityHydrationError, setReproducibilityHydrationError] = useState<string | null>(null);
  const [reproducibilityHydrationReload, setReproducibilityHydrationReload] = useState(0);
  const [exhaustive, setExhaustive] = useState<ExhaustiveLabResult | null>(null);
  const [exhaustiveHydrationStatus, setExhaustiveHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [exhaustiveHydrationError, setExhaustiveHydrationError] = useState<string | null>(null);
  const [exhaustiveHydrationReload, setExhaustiveHydrationReload] = useState(0);
  const [assurance, setAssurance] = useState<AssuranceCase | null>(null);
  const [assuranceHydrationStatus, setAssuranceHydrationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [assuranceHydrationError, setAssuranceHydrationError] = useState<string | null>(null);
  const [assuranceHydrationReload, setAssuranceHydrationReload] = useState(0);
  const [verificationBundleRecord, setVerificationBundleRecord] = useState<VerificationBundle | null>(null);
  const [expertCorrection, setExpertCorrection] = useState<ExpertCorrectionRevision | null>(null);
  const [lineage, setLineage] = useState<LineageGraph | null>(null);
  const [lineageStatus, setLineageStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [lineageError, setLineageError] = useState<string | null>(null);
  const [lineageObjectError, setLineageObjectError] = useState<string | null>(null);
  const [lineageRetryNode, setLineageRetryNode] = useState<LineageNode | null>(null);
  const [lineageReload, setLineageReload] = useState(0);
  const lineageOpenRequestRef = useRef(0);
  const [dataGovernanceObject, setDataGovernanceObject] = useState<DataGovernanceObject | null>(null);
  const [integrity, setIntegrity] = useState<ProjectIntegrityReport | null>(null);
  const [integrityStatus, setIntegrityStatus] = useState<"idle" | "loading" | "available" | "error">("idle");
  const [integrityError, setIntegrityError] = useState<string | null>(null);
  const [integrityReload, setIntegrityReload] = useState(0);
  const [selectedExpertCorrectionId, setSelectedExpertCorrectionId] = useState<string | null>(null);
  const datasetFileInputRef = useRef<HTMLInputElement>(null);
  const datasetFileSelectionId = useRef(0);
  const projectSessionRef = useRef<string | null>(null);
  const projectLifecycleRequestRef = useRef(0);
  const projectLifecycleInFlightRef = useRef(false);
  const projectWriteInFlightRef = useRef(false);
  const backendHealthRequestRef = useRef(0);
  const csvInspectionRequestRef = useRef(0);
  const csvDraftRevisionRef = useRef(0);
  const datasetMutationRequestRef = useRef(0);
  const datasetMutationInFlightRef = useRef(false);
  const pendingDatasetWriteRef = useRef<PendingDatasetWrite | null>(null);
  const generalizationMutationRequestRef = useRef(0);
  const generalizationMutationInFlightRef = useRef(false);
  const [generalizationMutationOperation, setGeneralizationMutationOperation] = useState<"declare" | "freeze" | null>(null);
  const scopeClassificationRequestRef = useRef(0);
  const artifactInventoryRequestRef = useRef(0);
  projectSessionRef.current = project?.session_id ?? null;
  function bindProjectSession<Arguments extends unknown[]>(sessionId: string, callback: (...args: Arguments) => void) {
    return (...args: Arguments) => {
      if (projectSessionRef.current === sessionId) callback(...args);
    };
  }
  function rememberRecentProject(value: ProjectSummary) {
    const next = [{ name: value.name, path: value.root }, ...recentProjects.filter((item) => item.path !== value.root)].slice(0, 8);
    setRecentProjects(next);
    setRecentProjectError(null);
    try { localStorage.setItem(RECENT_PROJECTS_STORAGE_KEY, JSON.stringify(next)); } catch { /* project open must not fail because browser storage is unavailable */ }
  }
  function forgetRecentProjects() {
    setRecentProjects([]);
    setRecentProjectError(null);
    try { localStorage.removeItem(RECENT_PROJECTS_STORAGE_KEY); } catch { /* keep the current session usable */ }
  }
  function forgetRecentProject(pathToForget: string) {
    const next = recentProjects.filter((item) => item.path !== pathToForget);
    setRecentProjects(next);
    setRecentProjectError(null);
    try { localStorage.setItem(RECENT_PROJECTS_STORAGE_KEY, JSON.stringify(next)); } catch { /* keep the current session usable */ }
  }
  function closeStaleProjectSession(sessionId: string) {
    void studioApi.closeProject(sessionId).catch(() => undefined);
  }
  async function checkBackendHealth() {
    const requestId = ++backendHealthRequestRef.current;
    setBackendStatus("checking");
    setBackendHealthError(null);
    setStatus("Connecting to backend…");
    try {
      await studioApi.health();
      if (requestId !== backendHealthRequestRef.current) return;
      setBackendStatus("available");
      setStatus("Backend connected");
    } catch (reason) {
      if (requestId !== backendHealthRequestRef.current) return;
      const message = reason instanceof Error ? reason.message : "Backend health check failed.";
      setBackendStatus("unavailable");
      setBackendHealthError(message);
      setStatus("Backend unavailable");
    }
  }
  async function openRecentProject(recent: RecentProject) {
    if (backendStatus !== "available" || projectLifecycleInFlightRef.current) return;
    projectLifecycleInFlightRef.current = true;
    setProjectLifecycleOperation("recent");
    const requestId = ++projectLifecycleRequestRef.current;
    setError(null);
    setRecentProjectError(null);
    try {
      const result = await studioApi.openProject(recent.path, readOnly);
      if (requestId !== projectLifecycleRequestRef.current) {
        closeStaleProjectSession(result.session_id);
        return;
      }
      setProject(result);
      setDescription(result.description ?? "");
      rememberRecentProject(result);
      setStatus(`Opened ${result.name}`);
    } catch (reason) {
      if (requestId !== projectLifecycleRequestRef.current) return;
      if (reason instanceof ProductApiError) {
        setRecentProjectError(`Could not reopen ${recent.path}: ${reason.message} If this project moved or was deleted, forget this entry or choose the folder again.`);
        return;
      }
      setError(reason instanceof Error ? reason.message : "Could not reopen this recent project.");
    } finally {
      projectLifecycleInFlightRef.current = false;
      setProjectLifecycleOperation(null);
    }
  }
  const refreshArtifactInventory = useCallback(async (sessionId: string) => {
    if (projectSessionRef.current !== sessionId) return;
    const requestId = ++artifactInventoryRequestRef.current;
    setArtifactsHydrationStatus("loading");
    setArtifactsHydrationError(null);
    try {
      const items = await studioApi.listArtifacts(sessionId);
      if (projectSessionRef.current !== sessionId || artifactInventoryRequestRef.current !== requestId) return;
      setArtifacts(items);
      setArtifactsHydrationStatus("loaded");
    } catch (reason) {
      if (projectSessionRef.current !== sessionId || artifactInventoryRequestRef.current !== requestId) return;
      setArtifacts([]);
      setArtifactsHydrationError(reason instanceof Error ? reason.message : "Project artifacts could not be verified.");
      setArtifactsHydrationStatus("error");
    }
  }, []);
  useEffect(() => {
    void checkBackendHealth();
  }, []);
  useEffect(() => {
    let active = true;
    if (!project) {
      artifactInventoryRequestRef.current += 1;
      setArtifacts([]);
      setArtifactsHydrationError(null);
      setArtifactsHydrationStatus("idle");
      return () => { active = false; };
    }
    const requestId = ++artifactInventoryRequestRef.current;
    setArtifacts([]);
    setArtifactsHydrationError(null);
    setArtifactsHydrationStatus("loading");
    studioApi.listArtifacts(project.session_id).then((items) => {
      if (!active || artifactInventoryRequestRef.current !== requestId) return;
      setArtifacts(items);
      setArtifactsHydrationStatus("loaded");
    }).catch((reason: unknown) => {
      if (!active || artifactInventoryRequestRef.current !== requestId) return;
      setArtifacts([]);
      setArtifactsHydrationError(reason instanceof Error ? reason.message : "Project artifacts could not be verified.");
      setArtifactsHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, artifactsHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setDatasetState(null);
      setDataset(null);
      setProfile(null);
      setDatasetStateStatus("idle");
      setDatasetStateError(null);
      setOverviewContextStatus("idle");
      setOverviewContextSessionId(null);
      setOverviewContextError(null);
      setFis(null);
      setFisEvaluation(null);
      setFisEvaluationStatus("idle");
      setFisEvaluationError(null);
      setPreviousFisEvaluation(null);
      setTrainingRun(null);
      setTrainingRuns([]);
      setTrainingRunsStatus("idle");
      setTrainingRunsError(null);
      setTrainingStudy(null);
      setTrainingStudyStatus("idle");
      setTrainingStudyError(null);
      setStabilityAnalysis(null);
      setStabilityAnalysisHydrationStatus("idle");
      setStabilityAnalysisHydrationError(null);
      setStabilityGatePolicy(null);
      setAnalysisEvaluation(null);
      setAnalysisEvaluationStatus("idle");
      setAnalysisEvaluationError(null);
      setValidationPolicyEvidenceStatus("idle");
      setValidationPolicyEvidenceError(null);
      setAnalysisComparison(null);
      setAnalysisComparisonHydrationStatus("idle");
      setAnalysisComparisonHydrationError(null);
      setCalibrationTransform(null);
      setDecisionThreshold(null);
      setFinalTestEvaluation(null);
      setFinalTestEvidenceStatus("idle");
      setFinalTestEvidenceError(null);
      setSliceAnalysis(null);
      setSliceAnalysisHydrationStatus("idle");
      setSliceAnalysisHydrationError(null);
      setTreeEvidence(null);
      setTreeEvidenceHydrationStatus("idle");
      setTreeEvidenceHydrationError(null);
      setExplanation(null);
      setExplanationHydrationStatus("idle");
      setExplanationHydrationError(null);
      setExplanationCheck(null);
      setExplanationCheckHydrationStatus("idle");
      setExplanationCheckHydrationError(null);
      setBehaviorSpec(null);
      setBehaviorResult(null);
      setBehaviorSpecResultStatus("idle");
      setBehaviorSpecResultError(null);
      setLineageBehaviorComparison(null);
      setSelectivePolicy(null);
      setReproducibility(null);
      setReproducibilityHydrationStatus("idle");
      setReproducibilityHydrationError(null);
      setExhaustive(null);
      setExhaustiveHydrationStatus("idle");
      setExhaustiveHydrationError(null);
      setAssurance(null);
      setAssuranceHydrationStatus("idle");
      setAssuranceHydrationError(null);
      setVerificationBundleRecord(null);
      setExpertCorrection(null);
      setGeneralization(null);
      setGeneralizationHydrationStatus("idle");
      setGeneralizationHydrationError(null);
      setScopeCandidateValue("");
      setScopeClassification(null);
      setLineage(null);
      setLineageStatus("idle");
      setLineageError(null);
      setLineageObjectError(null);
      setLineageRetryNode(null);
      setDataGovernanceObject(null);
      setIntegrity(null);
      setIntegrityStatus("idle");
      setIntegrityError(null);
      setSelectedExpertCorrectionId(null);
      return;
    }
    const newProjectSession = overviewContextSessionId !== project.session_id;
    setOverviewContextStatus("loading");
    setOverviewContextSessionId(project.session_id);
    setOverviewContextError(null);
    if (newProjectSession) {
      setDatasetState(null);
      setDataset(null);
      setProfile(null);
      setDatasetStateStatus("loading");
      setDatasetStateError(null);
      setTrainingRun(null);
      setTrainingRuns([]);
      setTrainingRunsStatus("loading");
      setTrainingRunsError(null);
      setTrainingStudy(null);
      setTrainingStudyStatus("loading");
      setTrainingStudyError(null);
      setStabilityGatePolicy(null);
      setCalibrationTransform(null);
      setDecisionThreshold(null);
      setSelectivePolicy(null);
      setValidationPolicyEvidenceStatus("loading");
      setValidationPolicyEvidenceError(null);
      setLineage(null);
      setLineageStatus("loading");
      setLineageError(null);
      setIntegrity(null);
      setIntegrityStatus("loading");
      setIntegrityError(null);
      setFisEvaluation(null);
      setFisEvaluationStatus("loading");
      setFisEvaluationError(null);
    }
    const resolveOptional = <T,>(request: Promise<T>) => request.then(
      (value) => ({ kind: "value" as const, value }),
      (reason: unknown) => reason instanceof ProductApiError && reason.status === 404
        ? ({ kind: "none" as const })
        : ({ kind: "error" as const, reason }),
    );
    Promise.all([
      resolveOptional(studioApi.getActiveFis(project.session_id)),
      resolveOptional(studioApi.getLatestTraining(project.session_id)),
    ]).then(([fisResult, runResult]) => {
      if (!active) return;
      if (fisResult.kind !== "error" || newProjectSession) setFis(fisResult.kind === "value" ? fisResult.value : null);
      if (runResult.kind !== "error" || newProjectSession) setTrainingRun((current) => runResult.kind === "value" ? (newProjectSession ? runResult.value : current ?? runResult.value) : null);
      const failures = [fisResult, runResult].filter((result) => result.kind === "error");
      if (failures.length) {
        const first = failures[0];
        setOverviewContextStatus("error");
        setOverviewContextError(first.kind === "error" && first.reason instanceof Error ? first.reason.message : "Saved project model/training context could not be verified.");
      } else {
        setOverviewContextStatus("loaded");
      }
    });
    return () => { active = false; };
  }, [project?.session_id, overviewContextReload]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setStabilityAnalysis(null);
      setStabilityAnalysisHydrationStatus("idle");
      setStabilityAnalysisHydrationError(null);
      return () => { active = false; };
    }
    setStabilityAnalysis(null);
    setStabilityAnalysisHydrationStatus("loading");
    setStabilityAnalysisHydrationError(null);
    studioApi.listStudyStabilityAnalyses(project.session_id).then((items) => {
      if (!active) return;
      const latest = items.at(-1) ?? null;
      setStabilityAnalysis(latest);
      setStabilityAnalysisHydrationStatus(latest ? "available" : "none");
    }).catch((reason: unknown) => {
      if (!active) return;
      setStabilityAnalysis(null);
      setStabilityAnalysisHydrationError(reason instanceof Error ? reason.message : "Saved StudyStabilityAnalysis could not be verified.");
      setStabilityAnalysisHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, stabilityAnalysisHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setTreeEvidence(null);
      setTreeEvidenceHydrationStatus("idle");
      setTreeEvidenceHydrationError(null);
      return () => { active = false; };
    }
    setTreeEvidence(null);
    setTreeEvidenceHydrationStatus("loading");
    setTreeEvidenceHydrationError(null);
    studioApi.getLatestTreePath(project.session_id).then((evidence) => {
      if (!active) return;
      setTreeEvidence(evidence);
      setTreeEvidenceHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setTreeEvidence(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setTreeEvidenceHydrationStatus("none");
        return;
      }
      setTreeEvidenceHydrationError(reason instanceof Error ? reason.message : "Saved TreePathEvidence could not be verified.");
      setTreeEvidenceHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, treeEvidenceHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setAnalysisComparison(null);
      setAnalysisComparisonHydrationStatus("idle");
      setAnalysisComparisonHydrationError(null);
      return () => { active = false; };
    }
    setAnalysisComparison(null);
    setAnalysisComparisonHydrationError(null);
    setAnalysisComparisonHydrationStatus("loading");
    studioApi.getLatestAnalysisComparison(project.session_id).then((value) => {
      if (!active) return;
      setAnalysisComparison(value);
      setAnalysisComparisonHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setAnalysisComparison(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setAnalysisComparisonHydrationStatus("none");
        return;
      }
      setAnalysisComparisonHydrationError(reason instanceof Error ? reason.message : "Saved validation comparison could not be verified.");
      setAnalysisComparisonHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, analysisComparisonHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setSliceAnalysis(null);
      setSliceAnalysisHydrationStatus("idle");
      setSliceAnalysisHydrationError(null);
      return () => { active = false; };
    }
    setSliceAnalysis(null);
    setSliceAnalysisHydrationError(null);
    setSliceAnalysisHydrationStatus("loading");
    studioApi.getLatestSliceAnalysis(project.session_id).then((value) => {
      if (!active) return;
      setSliceAnalysis(value);
      setSliceAnalysisHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setSliceAnalysis(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setSliceAnalysisHydrationStatus("none");
        return;
      }
      setSliceAnalysisHydrationError(reason instanceof Error ? reason.message : "Saved SliceAnalysis could not be verified.");
      setSliceAnalysisHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, sliceAnalysisHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setGeneralization(null);
      setGeneralizationHydrationStatus("idle");
      setGeneralizationHydrationError(null);
      return () => { active = false; };
    }
    setGeneralization(null);
    setGeneralizationHydrationError(null);
    setGeneralizationHydrationStatus("loading");
    studioApi.getActiveGeneralization(project.session_id).then((value) => {
      if (!active) return;
      setGeneralization(value);
      setGeneralizationHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setGeneralization(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setGeneralizationHydrationStatus("none");
        return;
      }
      setGeneralizationHydrationError(reason instanceof Error ? reason.message : "Saved GeneralizationContract could not be verified.");
      setGeneralizationHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, generalizationHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setExhaustive(null);
    setExhaustiveHydrationError(null);
    setExhaustiveHydrationStatus("loading");
    studioApi.getLatestExhaustiveLab(project.session_id).then((value) => {
      if (!active) return;
      setExhaustive(value);
      setExhaustiveHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setExhaustive(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setExhaustiveHydrationStatus("none");
        return;
      }
      setExhaustiveHydrationError(reason instanceof Error ? reason.message : "Saved exhaustive evidence could not be loaded.");
      setExhaustiveHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, exhaustiveHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setReproducibility(null);
    setReproducibilityHydrationError(null);
    setReproducibilityHydrationStatus("loading");
    studioApi.getLatestExplanationReproducibility(project.session_id).then((value) => {
      if (!active) return;
      setReproducibility(value);
      setReproducibilityHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setReproducibility(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setReproducibilityHydrationStatus("none");
        return;
      }
      setReproducibilityHydrationError(reason instanceof Error ? reason.message : "Saved reproducibility analysis could not be loaded.");
      setReproducibilityHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, reproducibilityHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setExplanation(null);
    setExplanationHydrationError(null);
    setExplanationHydrationStatus("loading");
    studioApi.getLatestExplanation(project.session_id).then((value) => {
      if (!active) return;
      setExplanation(value);
      setExplanationHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setExplanation(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setExplanationHydrationStatus("none");
        return;
      }
      setExplanationHydrationError(reason instanceof Error ? reason.message : "Saved explanation could not be loaded.");
      setExplanationHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, explanationHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setExplanationCheck(null);
    setExplanationCheckHydrationError(null);
    setExplanationCheckHydrationStatus("loading");
    studioApi.getLatestExplanationCheck(project.session_id).then((value) => {
      if (!active) return;
      setExplanationCheck(value);
      setExplanationCheckHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setExplanationCheck(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setExplanationCheckHydrationStatus("none");
        return;
      }
      setExplanationCheckHydrationError(reason instanceof Error ? reason.message : "Saved explanation check could not be loaded.");
      setExplanationCheckHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, explanationCheckHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setAssurance(null);
    setAssuranceHydrationError(null);
    setAssuranceHydrationStatus("loading");
    studioApi.getLatestAssuranceCase(project.session_id).then((result) => {
      if (!active) return;
      setAssurance(result);
      setAssuranceHydrationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setAssurance(null);
      if (reason instanceof ProductApiError && reason.status === 404) {
        setAssuranceHydrationStatus("none");
        return;
      }
      setAssuranceHydrationError(reason instanceof Error ? reason.message : "Saved AssuranceCase could not be loaded.");
      setAssuranceHydrationStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, assuranceHydrationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setBehaviorResult(null);
    setBehaviorSpec(null);
    setBehaviorSpecResultError(null);
    setBehaviorSpecResultStatus("loading");
    let resultLoaded = false;
    studioApi.getLatestBehaviorSpecResult(project.session_id).then(async (result) => {
      resultLoaded = true;
      const specs = await studioApi.listBehaviorSpecs(project.session_id);
      const spec = specs.find((candidate) => candidate.spec_id === result.spec_id);
      if (!spec) throw new Error(`Saved BehaviorSpec ${result.spec_id} referenced by result ${result.result_id} is missing.`);
      if (!active) return;
      setBehaviorResult(result);
      setBehaviorSpec(spec);
      setBehaviorSpecResultStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setBehaviorResult(null);
      setBehaviorSpec(null);
      if (!resultLoaded && reason instanceof ProductApiError && reason.status === 404) {
        setBehaviorSpecResultStatus("none");
        return;
      }
      setBehaviorSpecResultError(reason instanceof Error ? reason.message : "Saved BehaviorSpec evidence could not be loaded.");
      setBehaviorSpecResultStatus("error");
    });
    return () => { active = false; };
  }, [project?.session_id, behaviorSpecResultReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setFisEvaluation(null);
    setFisEvaluationStatus("loading");
    setFisEvaluationError(null);
    studioApi.getLatestFisTrace(project.session_id).then((evaluation) => {
      if (!active) return;
      setFisEvaluation(evaluation);
      setFisEvaluationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setFisEvaluation(null);
        setFisEvaluationStatus("none");
        return;
      }
      setFisEvaluationStatus("error");
      setFisEvaluationError(reason instanceof Error ? reason.message : "Saved FIS evaluation evidence could not be loaded.");
    });
    return () => { active = false; };
  }, [project?.session_id, fisEvaluationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setIntegrityStatus("loading");
    setIntegrityError(null);
    studioApi.getProjectIntegrity(project.session_id).then((report) => {
      if (!active) return;
      setIntegrity(report);
      setIntegrityStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      setIntegrityStatus("error");
      setIntegrityError(reason instanceof Error ? reason.message : "Project integrity could not be checked.");
    });
    return () => { active = false; };
  }, [project?.session_id, integrityReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setDatasetStateStatus("loading");
    setDatasetStateError(null);
    studioApi.getDatasetState(project.session_id).then((state) => {
      if (!active) return;
      const pendingWrite = pendingDatasetWriteRef.current;
      const pendingWriteMatches = pendingWrite?.sessionId === project.session_id
        && (
          pendingWrite.datasetFingerprint === state.contract.dataset_fingerprint
          || (
            pendingWrite.sourceArtifactSha256 === state.contract.source_artifact_sha256
            && pendingWrite.target === state.contract.target
            && pendingWrite.task === state.contract.task
            && pendingWrite.sourceFormat === state.contract.source_format
            && JSON.stringify(pendingWrite.idColumns) === JSON.stringify(state.contract.id_columns)
            && JSON.stringify(pendingWrite.excludedColumns) === JSON.stringify(state.contract.excluded_columns)
          )
        );
      if (pendingWriteMatches && pendingWrite) {
        const draftStillMatches = pendingWrite.draftKind === "csv_text"
          ? pendingWrite.draftRevision === csvDraftRevisionRef.current
          : pendingWrite.draftRevision === datasetFileSelectionId.current;
        if (draftStillMatches) {
          if (pendingWrite.draftKind === "file") {
            setPendingDatasetFile(null);
            setPendingDatasetProfile(null);
          }
          setError(null);
          setStatus(`The saved ${pendingWrite.sourceFormat.toUpperCase()} DatasetContract matches the pending request; its confirmation was restored.`);
        }
        pendingDatasetWriteRef.current = null;
      }
      setDatasetState(state);
      setProfile(state.profile);
      setDataset({ contract: state.contract, audit: state.audit });
      setTarget(state.contract.target);
      setTask(state.contract.task);
      setIdColumns(state.contract.id_columns.join(", "));
      setExcludedColumns(state.contract.excluded_columns.join(", "));
      setDatasetStateStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setDatasetState(null);
        setDataset(null);
        setProfile(null);
        setDatasetStateStatus("none");
        return;
      }
      setDatasetStateStatus("error");
      setDatasetStateError(reason instanceof Error ? reason.message : "Persisted DatasetContract could not be loaded.");
    });
    return () => { active = false; };
  }, [project?.session_id, datasetStateReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setTrainingStudyStatus("loading");
    setTrainingStudyError(null);
    studioApi.getLatestTrainingStudy(project.session_id).then((study) => {
      if (!active) return;
      setTrainingStudy(study);
      setTrainingStudyStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setTrainingStudy(null);
        setTrainingStudyStatus("none");
        return;
      }
      setTrainingStudyStatus("error");
      setTrainingStudyError(reason instanceof Error ? reason.message : "Saved TrainingStudy could not be restored.");
    });
    return () => { active = false; };
  }, [project?.session_id, trainingStudyReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setValidationPolicyEvidenceStatus("loading");
    setValidationPolicyEvidenceError(null);
    const optional = async <T,>(load: () => Promise<T>): Promise<{ value: T | null; error: string | null }> => {
      try {
        return { value: await load(), error: null };
      } catch (reason) {
        if (reason instanceof ProductApiError && reason.status === 404) return { value: null, error: null };
        return { value: null, error: reason instanceof Error ? reason.message : "Persisted policy evidence could not be loaded." };
      }
    };
    Promise.all([
      optional(() => studioApi.getLatestAnalysisCalibration(project.session_id)),
      optional(() => studioApi.getLatestAnalysisThreshold(project.session_id)),
      optional(() => studioApi.getLatestSelectivePolicy(project.session_id)),
      optional(() => studioApi.listStabilityGatePolicies(project.session_id)),
    ]).then(([calibration, threshold, selective, stabilityPolicies]) => {
      if (!active) return;
      setCalibrationTransform(calibration.value);
      setDecisionThreshold(threshold.value);
      setSelectivePolicy(selective.value);
      if (stabilityPolicies.value) setStabilityGatePolicy(stabilityPolicies.value.at(-1) ?? null);
      const errors = [calibration.error, threshold.error, selective.error, stabilityPolicies.error].filter((message): message is string => Boolean(message));
      if (errors.length) {
        setValidationPolicyEvidenceStatus("error");
        setValidationPolicyEvidenceError(errors.join(" · "));
      } else {
        setValidationPolicyEvidenceStatus("available");
      }
    });
    return () => { active = false; };
  }, [project?.session_id, validationPolicyEvidenceReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setAnalysisEvaluationStatus("loading");
    setAnalysisEvaluationError(null);
    studioApi.getLatestAnalysisEvaluation(project.session_id).then((evaluation) => {
      if (!active) return;
      setAnalysisEvaluation(evaluation);
      setAnalysisEvaluationStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setAnalysisEvaluation(null);
        setAnalysisEvaluationStatus("none");
        return;
      }
      setAnalysisEvaluationStatus("error");
      setAnalysisEvaluationError(reason instanceof Error ? reason.message : "Could not verify saved validation Evaluation.");
    });
    return () => { active = false; };
  }, [project?.session_id, analysisEvaluationReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setFinalTestEvidenceStatus("loading");
    setFinalTestEvidenceError(null);
    studioApi.getLatestFinalTestEvaluation(project.session_id).then((evaluation) => {
      if (!active) return;
      setFinalTestEvaluation(evaluation);
      setFinalTestEvidenceStatus("available");
    }).catch((reason: unknown) => {
      if (!active) return;
      if (reason instanceof ProductApiError && reason.status === 404) {
        setFinalTestEvaluation(null);
        setFinalTestEvidenceStatus("none");
        return;
      }
      setFinalTestEvidenceStatus("error");
      setFinalTestEvidenceError(reason instanceof Error ? reason.message : "Could not verify persisted final-test access.");
    });
    return () => { active = false; };
  }, [project?.session_id, finalTestEvidenceReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setTrainingRunsStatus("loading");
    setTrainingRunsError(null);
    studioApi.getTrainingRuns(project.session_id).then((runs) => {
      if (!active) return;
      setTrainingRuns(runs);
      setTrainingRunsStatus("loaded");
      const newest = [...runs].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))[0] ?? null;
      setTrainingRun((current) => current ?? newest);
    }).catch((reason: unknown) => {
      if (!active) return;
      setTrainingRunsStatus("error");
      setTrainingRunsError(reason instanceof Error ? reason.message : "Could not load saved training runs.");
    });
    return () => { active = false; };
  }, [project?.session_id, trainingRunsReload]);
  useEffect(() => {
    let active = true;
    if (!project) return () => { active = false; };
    setLineageStatus("loading");
    setLineageError(null);
    studioApi.getProjectLineage(project.session_id).then((graph) => {
      if (!active) return;
      setLineage(graph);
      setLineageStatus("loaded");
    }).catch((reason: unknown) => {
      if (!active) return;
      setLineageStatus("error");
      setLineageError(reason instanceof Error ? reason.message : "Persisted project lineage could not be loaded.");
    });
    return () => { active = false; };
  }, [
    project?.session_id,
    lineageReload,
    datasetState?.contract.dataset_fingerprint,
    fis?.semantic_hash,
    trainingRun?.run_id,
    trainingStudy?.study_id,
    analysisEvaluation?.evaluation_id,
    analysisComparison?.comparison_id,
    calibrationTransform?.calibration_id,
    decisionThreshold?.threshold_id,
    finalTestEvaluation?.final_test_id,
    sliceAnalysis?.analysis_id,
    treeEvidence?.evidence_id,
    explanation?.explanation_id,
    explanationCheck?.check_id,
    behaviorResult?.result_id,
    expertCorrection?.correction_id,
    generalization?.contract.contract_id,
    generalization?.contract.frozen_at,
  ]);
  async function openLineageNode(node: LineageNode) {
    if (!project) return;
    const requestId = ++lineageOpenRequestRef.current;
    const sessionId = project.session_id;
    const isCurrent = () => requestId === lineageOpenRequestRef.current && projectSessionRef.current === sessionId;
    const commit = <T,>(setter: (value: T) => void, value: T) => {
      if (!isCurrent()) return false;
      setter(value);
      return true;
    };
    const objectId = node.object_id;
    setError(null);
    setLineageObjectError(null);
    setLineageRetryNode(null);
    try {
      if (node.kind === "training_run" && objectId) {
        const value = await studioApi.getTrainingRun(sessionId, objectId);
        if (!commit(setTrainingRun, value)) return;
      } else if (node.kind === "fis" && objectId) {
        const revisions = await studioApi.getFisRevisions(sessionId);
        if (!isCurrent()) return;
        const spec = revisions.find((candidate) => candidate.fis_id === objectId);
        if (!spec) throw new Error(`FIS is no longer available: ${objectId}`);
        if (!commit(setFis, spec)) return;
      } else if (node.kind === "fis_revision") {
        const semanticHash = node.id.split(":").at(-1);
        const revisions = await studioApi.getFisRevisions(sessionId);
        if (!isCurrent()) return;
        const revision = revisions.find((candidate) => candidate.semantic_hash === semanticHash);
        if (!revision) throw new Error(`FIS revision is no longer available: ${semanticHash ?? node.id}`);
        if (!commit(setFis, revision)) return;
      } else if (node.kind === "study" && objectId) {
        const value = await studioApi.getTrainingStudy(sessionId, objectId);
        if (!commit(setTrainingStudy, value)) return;
        setTrainingStudyStatus("available");
      } else if (node.kind === "study_stability" && objectId) {
        const value = await studioApi.getStudyStabilityAnalysis(sessionId, objectId);
        if (!commit(setStabilityAnalysis, value)) return;
      } else if (node.kind === "evaluation" && objectId) {
        const value = await studioApi.getAnalysisEvaluation(sessionId, objectId);
        if (!commit(setAnalysisEvaluation, value)) return;
        setAnalysisEvaluationStatus("available");
      } else if (node.kind === "calibration" && objectId) {
        const value = await studioApi.getAnalysisCalibration(sessionId, objectId);
        if (!commit(setCalibrationTransform, value)) return;
      } else if (node.kind === "decision_threshold" && objectId) {
        const value = await studioApi.getAnalysisThreshold(sessionId, objectId);
        if (!commit(setDecisionThreshold, value)) return;
      } else if (node.kind === "stability_gate_policy" && objectId) {
        const value = await studioApi.getStabilityGatePolicy(sessionId, objectId);
        if (!commit(setStabilityGatePolicy, value)) return;
      } else if (node.kind === "selective_policy" && objectId) {
        const value = await studioApi.getSelectivePolicy(sessionId, objectId);
        if (!commit(setSelectivePolicy, value)) return;
      } else if (node.kind === "final_test_evaluation" && objectId) {
        const value = await studioApi.getFinalTestEvaluation(sessionId, objectId);
        if (!commit(setFinalTestEvaluation, value)) return;
        setFinalTestEvidenceStatus("available");
      } else if (node.kind === "comparison" && objectId) {
        const value = await studioApi.getAnalysisComparison(sessionId, objectId);
        if (!commit(setAnalysisComparison, value)) return;
      } else if (node.kind === "slice_analysis" && objectId) {
        const value = await studioApi.getSliceAnalysis(sessionId, objectId);
        if (!commit(setSliceAnalysis, value)) return;
      } else if (node.kind === "tree_path" && objectId) {
        const value = await studioApi.getTreePath(sessionId, objectId);
        if (!commit(setTreeEvidence, value)) return;
      } else if (node.kind === "explanation" && objectId) {
        const value = await studioApi.getExplanation(sessionId, objectId);
        if (!commit(setExplanation, value)) return;
      } else if (node.kind === "explanation_check" && objectId) {
        const value = await studioApi.getExplanationCheck(sessionId, objectId);
        if (!commit(setExplanationCheck, value)) return;
      } else if (node.kind === "generalization_contract" && objectId) {
        const value = await studioApi.getGeneralization(sessionId, objectId);
        if (!commit(setGeneralization, value)) return;
        setScopeClassification(null);
      } else if (node.kind === "expert_correction" && objectId) {
        const correction = await studioApi.getExpertCorrection(sessionId, objectId);
        if (!isCurrent()) return;
        const revisions = await studioApi.getFisRevisions(sessionId);
        if (!isCurrent()) return;
        const resultRevision = revisions.find((revision) => revision.semantic_hash === correction.result_semantic_hash);
        if (resultRevision && !commit(setFis, resultRevision)) return;
        if (!commit(setExpertCorrection, correction)) return;
        setSelectedExpertCorrectionId(objectId);
      } else if (node.kind === "split_contract" && objectId) {
        const value = await studioApi.getSplitContract(sessionId, objectId);
        if (!commit(setDataGovernanceObject, { kind: "split_contract", value })) return;
      } else if (node.kind === "transform_pipeline" && objectId) {
        const value = await studioApi.getTransformPipeline(sessionId, objectId);
        if (!commit(setDataGovernanceObject, { kind: "transform_pipeline", value })) return;
      } else if (node.kind === "leakage_audit" && objectId) {
        const value = await studioApi.getLeakageAudit(sessionId, objectId);
        if (!commit(setDataGovernanceObject, { kind: "leakage_audit", value })) return;
      } else if (node.kind === "behavior_spec" && objectId) {
        const specs = await studioApi.listBehaviorSpecs(sessionId);
        if (!isCurrent()) return;
        const spec = specs.find((candidate) => candidate.spec_id === objectId);
        if (!spec) throw new Error(`BehaviorSpec is no longer available: ${objectId}`);
        if (!commit(setBehaviorSpec, spec)) return;
        setBehaviorResult(null);
      } else if (node.kind === "behavior_spec_result" && objectId) {
        const results = await studioApi.listBehaviorResults(sessionId);
        if (!isCurrent()) return;
        const result = results.find((candidate) => candidate.result_id === objectId);
        if (!result) throw new Error(`BehaviorSpecResult is no longer available: ${objectId}`);
        const specs = await studioApi.listBehaviorSpecs(sessionId);
        if (!isCurrent()) return;
        const spec = specs.find((candidate) => candidate.spec_id === result.spec_id);
        if (!spec) throw new Error(`BehaviorSpec ${result.spec_id} for this result is no longer available`);
        if (!commit(setBehaviorSpec, spec) || !commit(setBehaviorResult, result)) return;
      } else if (node.kind === "behavior_revision_comparison" && objectId) {
        const comparisons = await studioApi.listBehaviorRevisionComparisons(sessionId);
        if (!isCurrent()) return;
        const comparison = comparisons.find((candidate) => candidate.comparison_id === objectId);
        if (!comparison) throw new Error(`Behavior revision comparison is no longer available: ${objectId}`);
        if (!commit(setLineageBehaviorComparison, comparison)) return;
      } else if (node.kind === "assurance_case" && objectId) {
        const value = await studioApi.getAssuranceCase(sessionId, objectId);
        if (!commit(setAssurance, value)) return;
        setAssuranceHydrationStatus("available");
        setAssuranceHydrationError(null);
      } else if (node.kind === "verification_bundle" && objectId) {
        const value = await studioApi.getVerificationBundle(sessionId, objectId);
        if (!commit(setVerificationBundleRecord, value)) return;
      } else if (node.kind === "explanation_reproducibility" && objectId) {
        const value = await studioApi.getExplanationReproducibility(sessionId, objectId);
        if (!commit(setReproducibility, value)) return;
      } else if (node.kind === "exhaustive_lab" && objectId) {
        const value = await studioApi.getExhaustiveLabResult(sessionId, objectId);
        if (!commit(setExhaustive, value)) return;
      } else if (node.kind === "dataset") {
        if (!commit(setDataGovernanceObject, null)) return;
      }
      if (!isCurrent()) return;
      setActive(node.target);
      setStatus(`Opened lineage object: ${node.label}`);
    } catch (reason) {
      if (!isCurrent()) return;
      setLineageRetryNode(node);
      setLineageObjectError(reason instanceof Error ? reason.message : "Could not open the selected persisted object.");
      setError(reason instanceof Error ? reason.message : "Could not open lineage object");
    }
  }
  const toggle = (panel: Panels) =>
    setCollapsed((current) => ({ ...current, [panel]: !current[panel] }));
  async function submit(event: FormEvent, operation: "create" | "open") {
    event.preventDefault();
    if (backendStatus !== "available" || projectLifecycleInFlightRef.current) return;
    setProjectFormError(null);
    if (!path.trim()) {
      setProjectFormError("Enter a project folder path before creating or opening a project.");
      return;
    }
    if (operation === "create" && !name.trim()) {
      setProjectFormError("Enter a project name before creating a project.");
      return;
    }
    projectLifecycleInFlightRef.current = true;
    setProjectLifecycleOperation(operation);
    const requestId = ++projectLifecycleRequestRef.current;
    setError(null);
    try {
      const result =
        operation === "create"
          ? await studioApi.createProject(path, name)
          : await studioApi.openProject(path, readOnly);
      if (requestId !== projectLifecycleRequestRef.current) {
        closeStaleProjectSession(result.session_id);
        return;
      }
      setProject(result);
      setDescription(result.description ?? "");
      rememberRecentProject(result);
      setStatus(
        `${operation === "create" ? "Created" : "Opened"} ${result.name}`,
      );
    } catch (reason) {
      if (requestId !== projectLifecycleRequestRef.current) return;
      const message = reason instanceof Error ? reason.message : "Unknown request failure";
      setProjectFormError(operation === "create" && message.includes("Refusing to create a project over an existing path:")
        ? `A project already exists at this path. Choose Open project to reopen it, or enter a different path.`
        : message);
    } finally {
      projectLifecycleInFlightRef.current = false;
      setProjectLifecycleOperation(null);
    }
  }
  async function save() {
    if (!project || projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || datasetMutationInFlightRef.current) return;
    const sessionId = project.session_id;
    projectWriteInFlightRef.current = true;
    setProjectWriteOperation("save");
    setError(null);
    try {
      const result = await studioApi.saveProject(sessionId);
      if (projectSessionRef.current !== sessionId) return;
      setProject(result);
      setStatus(`Saved ${result.name}`);
    } catch (reason) {
      if (projectSessionRef.current !== sessionId) return;
      setError(
        reason instanceof Error ? reason.message : "Unknown request failure",
      );
    } finally {
      projectWriteInFlightRef.current = false;
      setProjectWriteOperation(null);
    }
  }
  async function updateDescription() {
    if (!project || project.read_only || projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || datasetMutationInFlightRef.current) return;
    const sessionId = project.session_id;
    projectWriteInFlightRef.current = true;
    setProjectWriteOperation("description");
    try {
      const result = await studioApi.updateProjectMetadata(
        sessionId,
        description,
      );
      if (projectSessionRef.current !== sessionId) return;
      setProject(result);
      setStatus(`Updated ${result.name}`);
    } catch (reason) {
      if (projectSessionRef.current !== sessionId) return;
      setError(
        reason instanceof Error ? reason.message : "Unknown request failure",
      );
    } finally {
      projectWriteInFlightRef.current = false;
      setProjectWriteOperation(null);
    }
  }
  async function close() {
    if (projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || datasetMutationInFlightRef.current) return;
    const requestId = ++projectLifecycleRequestRef.current;
    datasetFileSelectionId.current += 1;
    csvInspectionRequestRef.current += 1;
    datasetMutationRequestRef.current += 1;
    generalizationMutationRequestRef.current += 1;
    scopeClassificationRequestRef.current += 1;
    if (project) {
      try {
        await studioApi.closeProject(project.session_id);
      } catch {
        /* cleanup is best effort for a local session */
      }
    }
    if (requestId !== projectLifecycleRequestRef.current) return;
    setProject(null);
    setDatasetState(null);
    setPendingDatasetFile(null);
    setPendingDatasetProfile(null);
    setIdColumns("");
    setExcludedColumns("");
    pendingDatasetWriteRef.current = null;
    setInspectingDatasetFile(false);
    setImportingDatasetFile(false);
    setConfirmingCsvDataset(false);
    setFis(null);
    setFisEvaluation(null);
    setPreviousFisEvaluation(null);
    setTrainingRun(null);
    setTrainingStudy(null);
    setAnalysisEvaluation(null);
    setAnalysisComparison(null);
    setCalibrationTransform(null);
    setDecisionThreshold(null);
    setGeneralization(null);
    setLineage(null);
    setStatus("Project closed");
  }
  async function inspectCsv() {
    if (!project || (datasetStateStatus !== "none" && datasetStateStatus !== "available")) return;
    const requestId = ++csvInspectionRequestRef.current;
    const sessionId = project.session_id;
    const isCurrent = () => requestId === csvInspectionRequestRef.current && projectSessionRef.current === sessionId;
    try {
      const inspected = (await studioApi.inspectCsv(sessionId, csvText)).profile;
      if (!isCurrent()) return;
      const availableColumns = new Set(inspected.columns.map((column) => column.name));
      const retainedRoles = (value: string) => value.split(",").map((column) => column.trim()).filter((column) => availableColumns.has(column));
      setProfile(inspected);
      setTarget((current) => availableColumns.has(current) ? current : "");
      setIdColumns((current) => retainedRoles(current).join(", ") || inspected.id_candidates.join(", "));
      setExcludedColumns((current) => retainedRoles(current).join(", "));
      setStatus("Dataset schema inspected");
    } catch (reason) {
      if (!isCurrent()) return;
      setError(
        reason instanceof Error ? reason.message : "Dataset inspection failed",
      );
    }
  }
  function updateCsvText(value: string) {
    csvInspectionRequestRef.current += 1;
    csvDraftRevisionRef.current += 1;
    if (pendingDatasetFile) {
      datasetFileSelectionId.current += 1;
      setPendingDatasetFile(null);
      setPendingDatasetProfile(null);
      setInspectingDatasetFile(false);
      setTarget("");
      setIdColumns("");
      setExcludedColumns("");
      setStatus("CSV changed; file selection cleared. Inspect the CSV before confirming");
    }
    setCsvText(value);
    if (profile) {
      setProfile(null);
      setError(null);
      setStatus("CSV changed; inspect again before confirming");
    }
  }
  function columnRole(name: string): "target" | "id" | "excluded" | "feature" {
    if (name === target) return "target";
    if (idColumns.split(",").some((column) => column.trim() === name)) return "id";
    if (excludedColumns.split(",").some((column) => column.trim() === name)) return "excluded";
    return "feature";
  }
  function assignColumnRole(name: string, role: "target" | "id" | "excluded" | "feature") {
    const withoutName = (value: string) => value.split(",").map((column) => column.trim()).filter((column) => column && column !== name);
    const ids = withoutName(idColumns);
    const excluded = withoutName(excludedColumns);
    if (role === "target") setTarget(name);
    else if (target === name) setTarget("");
    if (role === "id") ids.push(name);
    if (role === "excluded") excluded.push(name);
    setIdColumns(ids.join(", "));
    setExcludedColumns(excluded.join(", "));
  }
  async function confirmCsv() {
    if (!project || datasetMutationInFlightRef.current || confirmingCsvDataset || importingDatasetFile || projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || (datasetStateStatus !== "none" && datasetStateStatus !== "available")) return;
    datasetMutationInFlightRef.current = true;
    const requestId = ++datasetMutationRequestRef.current;
    const sessionId = project.session_id;
    const previousDatasetFingerprint = datasetState?.contract.dataset_fingerprint ?? null;
    const draftProfile = profile;
    const isCurrent = () => requestId === datasetMutationRequestRef.current && projectSessionRef.current === sessionId;
    setConfirmingCsvDataset(true);
    setDatasetStateStatus("loading");
    setError(null);
    setStatus("Saving dataset contract");
    let confirmationResponseReceived = false;
    let sourceArtifactSha256: string | null = null;
    const requestedIdColumns = idColumns.split(",").map((column) => column.trim()).filter(Boolean);
    const requestedExcludedColumns = excludedColumns.split(",").map((column) => column.trim()).filter(Boolean);
    try {
      const csvBytes = new TextEncoder().encode(csvText);
      const digestBuffer = new Uint8Array(csvBytes.byteLength);
      digestBuffer.set(csvBytes);
      sourceArtifactSha256 = await sha256Hex(digestBuffer.buffer);
      if (!isCurrent()) return;
      pendingDatasetWriteRef.current = {
        sessionId,
        sourceArtifactSha256,
        target,
        task,
        idColumns: requestedIdColumns,
        excludedColumns: requestedExcludedColumns,
        sourceFormat: "csv",
        draftKind: "csv_text",
        draftRevision: csvDraftRevisionRef.current,
      };
      const confirmed = await studioApi.confirmCsv(
        sessionId,
        csvText,
        target,
        task,
        requestedIdColumns,
        requestedExcludedColumns,
      );
      confirmationResponseReceived = true;
      if (!isCurrent()) return;
      setDataset(confirmed);
      const persisted = await studioApi.getDatasetState(sessionId);
      if (!isCurrent()) return;
      setDatasetState(persisted);
      setProfile(persisted.profile);
      setDatasetStateStatus("available");
      await refreshArtifactInventory(sessionId);
      setStatus("Dataset bytes, profile, contract and audit saved");
    } catch (reason) {
      if (!isCurrent()) return;
      if (!confirmationResponseReceived && sourceArtifactSha256) {
        try {
          const persisted = await studioApi.getDatasetState(sessionId);
          if (!isCurrent()) return;
          const sameContract = persisted.contract.source_artifact_sha256 === sourceArtifactSha256
            && persisted.contract.target === target
            && persisted.contract.task === task
            && JSON.stringify(persisted.contract.id_columns) === JSON.stringify(requestedIdColumns)
            && JSON.stringify(persisted.contract.excluded_columns) === JSON.stringify(requestedExcludedColumns)
            && persisted.contract.source_format === "csv";
          setDatasetState(persisted);
          setDataset({ contract: persisted.contract, audit: persisted.audit });
          setProfile(persisted.profile);
          setDatasetStateStatus("available");
          setDatasetStateError(null);
          if (sameContract) {
            setError(null);
            setStatus("The CSV DatasetContract was saved; restored confirmation after the response was lost");
            void refreshArtifactInventory(sessionId);
            return;
          }
          if (reason instanceof ProductApiError && reason.status === 422
            && persisted.contract.dataset_fingerprint === previousDatasetFingerprint) {
            pendingDatasetWriteRef.current = null;
            setProfile(draftProfile);
            setError(reason.message);
            setStatus("Dataset confirmation rejected; correct the draft roles and retry");
            return;
          }
          setError("The confirmation response was lost and the saved DatasetContract does not match the current CSV and settings. No second confirmation was sent; review the saved dataset.");
          setStatus("CSV confirmation outcome could not be matched to the saved dataset");
          return;
        } catch (readReason) {
          if (reason instanceof ProductApiError && reason.status === 422
            && previousDatasetFingerprint === null
            && readReason instanceof ProductApiError && readReason.status === 404) {
            pendingDatasetWriteRef.current = null;
            setDatasetState(null);
            setDataset(null);
            setDatasetStateStatus("none");
            setDatasetStateError(null);
            setError(reason.message);
            setStatus("Dataset confirmation rejected; correct the draft roles and retry");
            return;
          }
          /* Fall through to the explicit retry state if the persisted state cannot be read either. */
        }
      }
      setDatasetStateStatus("error");
      setDatasetStateError(reason instanceof Error ? reason.message : "Dataset state could not be confirmed.");
      setError(
        reason instanceof Error
          ? reason.message
          : "Dataset confirmation failed",
      );
    } finally {
      datasetMutationInFlightRef.current = false;
      if (isCurrent()) setConfirmingCsvDataset(false);
    }
  }
  async function selectDatasetFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    const selectionId = ++datasetFileSelectionId.current;
    if (file && file.size > MAX_DATASET_UPLOAD_BYTES) {
      setPendingDatasetFile(null);
      setPendingDatasetProfile(null);
      setError("Dataset file exceeds the 5 MB import limit. Choose a smaller CSV or XLSX file.");
      setStatus("Oversized file was not read or uploaded");
      return;
    }
    setPendingDatasetFile(file ?? null);
    setPendingDatasetProfile(null);
    setInspectingDatasetFile(false);
    setError(null);
    if (!project || !file || (datasetStateStatus !== "none" && datasetStateStatus !== "available")) return;
    csvInspectionRequestRef.current += 1;
    setProfile(null);
    setTarget("");
    setIdColumns("");
    setExcludedColumns("");
    setInspectingDatasetFile(true);
    setStatus(`Inspecting ${file.name} without saving it`);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (const byte of bytes) binary += String.fromCharCode(byte);
      const inspected = await studioApi.inspectDatasetFile(project.session_id, file.name, btoa(binary));
      if (selectionId !== datasetFileSelectionId.current) return;
      setPendingDatasetProfile(inspected.profile);
      setStatus(`${file.name} inspected; choose a target and confirm to save`);
    } catch (reason) {
      if (selectionId !== datasetFileSelectionId.current) return;
      setError(reason instanceof Error ? reason.message : "Dataset file inspection failed");
      setStatus(`${file.name} could not be inspected`);
    } finally {
      if (selectionId === datasetFileSelectionId.current) setInspectingDatasetFile(false);
    }
  }
  async function importDatasetFile() {
    if (datasetMutationInFlightRef.current || projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || importingDatasetFile || confirmingCsvDataset || inspectingDatasetFile || !project || !pendingDatasetFile || !pendingDatasetProfile || !target.trim() || (datasetStateStatus !== "none" && datasetStateStatus !== "available")) return;
    datasetMutationInFlightRef.current = true;
    const requestId = ++datasetMutationRequestRef.current;
    const sessionId = project.session_id;
    const previousDatasetFingerprint = datasetState?.contract.dataset_fingerprint ?? null;
    const isCurrent = () => requestId === datasetMutationRequestRef.current && projectSessionRef.current === sessionId;
    const file = pendingDatasetFile;
    setImportingDatasetFile(true);
    setDatasetStateStatus("loading");
    setError(null);
    setStatus(`Importing ${file.name}`);
    let importResponseReceived = false;
    let sourceArtifactSha256: string | null = null;
    const requestedIdColumns = idColumns.split(",").map((column) => column.trim()).filter(Boolean);
    const requestedExcludedColumns = excludedColumns.split(",").map((column) => column.trim()).filter(Boolean);
    try {
      const fileBytes = await file.arrayBuffer();
      const bytes = new Uint8Array(fileBytes);
      if (!isCurrent()) return;
      sourceArtifactSha256 = await sha256Hex(fileBytes);
      pendingDatasetWriteRef.current = {
        sessionId,
        sourceArtifactSha256,
        target,
        task,
        idColumns: requestedIdColumns,
        excludedColumns: requestedExcludedColumns,
        sourceFormat: file.name.toLowerCase().endsWith(".xlsx") ? "xlsx" : "csv",
        draftKind: "file",
        draftRevision: datasetFileSelectionId.current,
      };
      let binary = "";
      for (const byte of bytes) binary += String.fromCharCode(byte);
      const confirmed = await studioApi.importDataset(
        sessionId,
        file.name,
        btoa(binary),
        target,
        task,
        requestedIdColumns,
        requestedExcludedColumns,
      );
      importResponseReceived = true;
      if (!isCurrent()) return;
      if (pendingDatasetWriteRef.current?.sessionId === sessionId
        && pendingDatasetWriteRef.current.draftRevision === datasetFileSelectionId.current) {
        pendingDatasetWriteRef.current.datasetFingerprint = confirmed.contract.dataset_fingerprint;
      }
      setDataset(confirmed);
      const persisted = await studioApi.getDatasetState(sessionId);
      if (!isCurrent()) return;
      setDatasetState(persisted);
      setDatasetStateStatus("available");
      setProfile(persisted.profile);
      await refreshArtifactInventory(sessionId);
      setStatus(`${file.name} saved as a verified dataset artifact`);
      setPendingDatasetFile(null);
      setPendingDatasetProfile(null);
      pendingDatasetWriteRef.current = null;
      setError(null);
    } catch (reason) {
      if (!isCurrent()) return;
      if (!importResponseReceived && sourceArtifactSha256) {
        try {
          const persisted = await studioApi.getDatasetState(sessionId);
          if (!isCurrent()) return;
          const sameContract = persisted.contract.source_artifact_sha256 === sourceArtifactSha256
            && persisted.contract.target === target
            && persisted.contract.task === task
            && JSON.stringify(persisted.contract.id_columns) === JSON.stringify(requestedIdColumns)
            && JSON.stringify(persisted.contract.excluded_columns) === JSON.stringify(requestedExcludedColumns);
          setDatasetState(persisted);
          setDataset({ contract: persisted.contract, audit: persisted.audit });
          setProfile(persisted.profile);
          setDatasetStateStatus("available");
          setDatasetStateError(null);
          if (sameContract) {
            const pendingWrite = pendingDatasetWriteRef.current;
            pendingDatasetWriteRef.current = null;
            if (pendingWrite?.draftKind === "file"
              && pendingWrite?.draftRevision === datasetFileSelectionId.current) {
              setPendingDatasetFile(null);
              setPendingDatasetProfile(null);
            }
            setError(null);
            setStatus(`${file.name} is present in the project; restored its confirmation after the upload response was lost`);
            void refreshArtifactInventory(sessionId);
            return;
          }
          if (reason instanceof ProductApiError && reason.status === 422
            && persisted.contract.dataset_fingerprint === previousDatasetFingerprint) {
            pendingDatasetWriteRef.current = null;
            setError(reason.message);
            setStatus("Dataset import rejected; correct the draft roles and retry");
            return;
          }
          setError("The upload response was lost and the saved DatasetContract does not match this file and target. The file was not uploaded again; review the saved dataset before retrying.");
          setStatus("Upload outcome could not be matched to the saved dataset");
          return;
        } catch (readReason) {
          if (reason instanceof ProductApiError && reason.status === 422
            && previousDatasetFingerprint === null
            && readReason instanceof ProductApiError && readReason.status === 404) {
            pendingDatasetWriteRef.current = null;
            setDatasetState(null);
            setDataset(null);
            setDatasetStateStatus("none");
            setDatasetStateError(null);
            setError(reason.message);
            setStatus("Dataset import rejected; correct the draft roles and retry");
            return;
          }
          /* Fall through to the explicit retry state if the persisted state cannot be read either. */
        }
      }
      setDatasetStateStatus("error");
      setDatasetStateError(reason instanceof Error ? reason.message : "Imported dataset state could not be restored.");
      setError(reason instanceof Error ? reason.message : "Dataset file import failed");
    } finally {
      datasetMutationInFlightRef.current = false;
      if (isCurrent()) setImportingDatasetFile(false);
    }
  }
  async function createGeneralization() {
    if (!project || projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || datasetMutationInFlightRef.current) return;
    generalizationMutationInFlightRef.current = true;
    setGeneralizationMutationOperation("declare");
    const requestId = ++generalizationMutationRequestRef.current;
    const sessionId = project.session_id;
    const isCurrent = () => requestId === generalizationMutationRequestRef.current && projectSessionRef.current === sessionId;
    try {
      const field = scopeField || datasetState?.contract.id_columns[0] || datasetState?.contract.feature_columns[0] || "";
      const parseValues = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);
      const supported = parseValues(supportedScopeValues);
      const forbidden = parseValues(forbiddenScopeValues);
      const created = await studioApi.createGeneralization(
        sessionId,
        intendedUse,
        noveltyAxis,
        {
          supportedScope: field && supported.length ? [{ field, operator: "in", value: supported, rationale: "Declared supported deployment scope" }] : [],
          forbiddenScope: field && forbidden.length ? [{ field, operator: "in", value: forbidden, rationale: "Declared forbidden deployment scope" }] : [],
          unsupportedAction,
        },
      );
      if (!isCurrent()) return;
      setGeneralization(created);
      setGeneralizationHydrationStatus("available");
      setGeneralizationHydrationError(null);
      setScopeClassification(null);
      setStatus("Generalization contract declared");
    } catch (reason) {
      if (!isCurrent()) return;
      setError(
        reason instanceof Error
          ? reason.message
          : "Generalization declaration failed",
      );
    } finally {
      generalizationMutationInFlightRef.current = false;
      setGeneralizationMutationOperation(null);
    }
  }
  async function freezeGeneralization() {
    if (!project || !generalization || projectWriteInFlightRef.current || generalizationMutationInFlightRef.current || datasetMutationInFlightRef.current) return;
    generalizationMutationInFlightRef.current = true;
    setGeneralizationMutationOperation("freeze");
    const requestId = ++generalizationMutationRequestRef.current;
    const sessionId = project.session_id;
    const contractId = generalization.contract.contract_id;
    const isCurrent = () => requestId === generalizationMutationRequestRef.current && projectSessionRef.current === sessionId;
    try {
      const frozen = await studioApi.freezeGeneralization(sessionId, contractId);
      if (!isCurrent()) return;
      setGeneralization(frozen);
      setGeneralizationHydrationStatus("available");
      setGeneralizationHydrationError(null);
      setStatus("Generalization contract frozen");
    } catch (reason) {
      if (!isCurrent()) return;
      setError(
        reason instanceof Error
          ? reason.message
          : "Generalization freeze failed",
      );
    } finally {
      generalizationMutationInFlightRef.current = false;
      setGeneralizationMutationOperation(null);
    }
  }
  async function checkScope(candidateMode: "preview" | "candidate") {
    if (!project || generalizationHydrationStatus !== "available" || !generalization || !datasetState?.preview.length) return;
    const requestId = ++scopeClassificationRequestRef.current;
    const sessionId = project.session_id;
    const contractId = generalization.contract.contract_id;
    const isCurrent = () => requestId === scopeClassificationRequestRef.current && projectSessionRef.current === sessionId;
    try {
      const metadata = { ...datasetState.preview[0] };
      if (candidateMode === "candidate") {
        const field = scopeField || datasetState.contract.id_columns[0] || datasetState.contract.feature_columns[0] || "";
        if (!field) throw new Error("Choose a scope field first.");
        if (!scopeCandidateValue.trim()) throw new Error("Enter a candidate scope value.");
        const sourceValue = metadata[field];
        const numericCandidate = Number(scopeCandidateValue);
        metadata[field] = typeof sourceValue === "number" && Number.isFinite(numericCandidate)
          ? numericCandidate
          : scopeCandidateValue.trim();
      }
      const result = await studioApi.classifyGeneralizationScope(sessionId, contractId, metadata);
      if (!isCurrent()) return;
      setScopeClassification(result);
      setStatus(candidateMode === "candidate" ? "Candidate classified against declared generalization scope" : "Preview row classified against declared generalization scope");
    } catch (reason) {
      if (!isCurrent()) return;
      setError(reason instanceof Error ? reason.message : "Scope classification failed");
    }
  }
  const inspector = project ? (
    <>
      <dl className="properties-list">
        <dt>Project ID</dt>
        <dd>ID: {project.project_id}</dd>
        <dt>Schema</dt>
        <dd>v{project.schema_version}</dd>
        <dt>Location</dt>
        <dd className="mono">{project.root}</dd>
      </dl>
      <label className="field-label">
        Description
        <TextInput
          aria-label="Description"
          value={description}
          disabled={project.read_only || projectWriteOperation !== null || generalizationMutationOperation !== null || confirmingCsvDataset || importingDatasetFile}
          onUpdate={setDescription}
          placeholder="Project description"
        />
      </label>
      <Button
        view="outlined"
        size="m"
        disabled={project.read_only || projectWriteOperation !== null || generalizationMutationOperation !== null || confirmingCsvDataset || importingDatasetFile}
        onClick={updateDescription}
        data-ruflex-action="project.description.update"
      >
        {projectWriteOperation === "description" ? "Updating description…" : "Update description"}
      </Button>
      <p className="property-description">
        Description: {project.description ?? "None"}
      </p>
      <div className="artifact-details">
        <strong>Artifacts</strong>
        {artifactsHydrationStatus === "loading" && <span role="status">Loading project artifacts…</span>}
        {artifactsHydrationStatus === "error" && <div className="error" role="alert" data-testid="artifact-hydration-error"><span>Project artifacts could not be verified. {artifactsHydrationError}</span><Button view="outlined" size="s" onClick={() => setArtifactsHydrationReload((current) => current + 1)}>Retry artifact list</Button></div>}
        {artifactsHydrationStatus === "loaded" && artifacts.length ? (
          artifacts.map((artifact) => (
            <div key={artifact.sha256} className="mono">
              {artifact.sha256.slice(0, 12)} · {artifact.size_bytes} B ·{" "}
              {artifact.source_kind}
            </div>
          ))
        ) : artifactsHydrationStatus === "loaded" ? (
          <span>No immutable artifacts yet.</span>
        ) : null}
      </div>
    </>
  ) : (
    <EmptyState title="No selection">
      Open a project to inspect canonical properties.
    </EmptyState>
  );
  const explorer = (
    <ProjectExplorer
      projectName={project?.name}
      dataset={datasetState}
      fis={fis}
      trainingRun={trainingRun}
      trainingStudy={trainingStudy}
      stabilityAnalysis={stabilityAnalysis}
      stabilityAnalysisHydrationStatus={stabilityAnalysisHydrationStatus}
      stabilityAnalysisHydrationError={stabilityAnalysisHydrationError}
      onRetryStabilityAnalysis={() => setStabilityAnalysisHydrationReload((current) => current + 1)}
      stabilityGatePolicy={stabilityGatePolicy}
      evaluation={fisEvaluation}
      evaluationStatus={fisEvaluationStatus}
      evaluationError={fisEvaluationError}
      onRetryEvaluation={() => setFisEvaluationReload((current) => current + 1)}
      analysisEvaluation={analysisEvaluation}
      analysisComparison={analysisComparison}
      calibrationTransform={calibrationTransform}
      decisionThreshold={decisionThreshold}
      finalTestEvaluation={finalTestEvaluation}
      sliceAnalysis={sliceAnalysis}
      generalization={generalization}
      treeEvidence={treeEvidence}
      treeEvidenceHydrationStatus={treeEvidenceHydrationStatus}
      treeEvidenceHydrationError={treeEvidenceHydrationError}
      onRetryTreeEvidence={() => setTreeEvidenceHydrationReload((current) => current + 1)}
      explanation={explanation}
      explanationCheck={explanationCheck}
      behaviorResult={behaviorResult}
      reproducibility={reproducibility}
      exhaustive={exhaustive}
      assurance={assurance}
      expertCorrection={expertCorrection}
      artifacts={artifacts}
      selected={active}
      onSelect={setActive}
    />
  );
  const datasetStateResolved = datasetStateStatus === "none" || datasetStateStatus === "available";
  return (
    <AppShell
      theme={theme}
      setTheme={setTheme}
      active={active}
      setActive={setActive}
      explorer={explorer}
      explorerCollapsed={collapsed.explorer}
      toggleExplorer={() => toggle("explorer")}
      inspectorCollapsed={collapsed.inspector}
      toggleInspector={() => toggle("inspector")}
      bottomCollapsed={collapsed.bottom}
      toggleBottom={() => toggle("bottom")}
      projectName={project?.name}
      readOnly={project?.read_only}
      saving={projectWriteOperation === "save"}
      saveDisabled={projectWriteOperation !== null || generalizationMutationOperation !== null || confirmingCsvDataset || importingDatasetFile}
      closeDisabled={projectWriteOperation !== null || generalizationMutationOperation !== null || confirmingCsvDataset || importingDatasetFile}
      status={status}
      error={error}
      onSave={save}
      onClose={close}
      inspector={inspector}
    >
      <div className="workspace-header">
        <div>
          <span className="eyebrow">{active}</span>
          <h1>{project ? project.name : "Create or open a RuFLEX project"}</h1>
          <p>
            Evidence-centered model engineering · persisted data, fuzzy models,
            real training and validation
          </p>
        </div>
        {project && (
          <StatusBadge tone={project.read_only ? "warning" : "success"}>
            {project.read_only
              ? "Read-only session"
              : "Canonical workspace open"}
          </StatusBadge>
        )}
      </div>
      {!project ? (
        <section className="project-start">
          <form onSubmit={(event) => submit(event, "create")}>
            <label className="field-label">
              Project path
              <TextInput
                aria-label="Project path"
                value={path}
                onUpdate={(value) => { setPath(value); setProjectFormError(null); }}
                placeholder="/path/to/Pump-01"
              />
            </label>
            <label className="field-label">
              Project name
              <TextInput
                aria-label="Project name"
                value={name}
                onUpdate={(value) => { setName(value); setProjectFormError(null); }}
                placeholder="Pump-01"
              />
            </label>
            <label className="check-label">
              <input
                aria-label="Read-only"
                type="checkbox"
                checked={readOnly}
                onChange={(event) => setReadOnly(event.target.checked)}
              />{" "}
              Open read-only
            </label>
            <div className="form-actions">
              <Button view="action" type="submit" data-ruflex-action="project.create" disabled={backendStatus !== "available" || projectLifecycleOperation !== null}>
                {projectLifecycleOperation === "create" ? "Creating project…" : "Create project"}
              </Button>
              <Button
                view="outlined"
                type="button"
                data-ruflex-action="project.open"
                disabled={backendStatus !== "available" || projectLifecycleOperation !== null}
                onClick={(event) =>
                  submit(event as unknown as FormEvent, "open")
                }
              >
                {projectLifecycleOperation === "open" ? "Opening project…" : "Open project"}
              </Button>
            </div>
          </form>
          {projectFormError && <div className="error" role="alert" data-testid="project-form-error">{projectFormError}</div>}
          {recentProjects.length > 0 && <section className="recent-projects" aria-label="Recent projects">
            <div className="recent-projects-heading"><strong>Recent projects</strong><Button view="outlined" size="s" type="button" onClick={forgetRecentProjects}>Forget history</Button></div>
            <div className="recent-project-list">{recentProjects.map((recent) => <div key={recent.path} className="recent-project-row">
              <button type="button" className="recent-project-item" onClick={() => void openRecentProject(recent)} disabled={backendStatus !== "available" || projectLifecycleOperation !== null}>
                <span>{recent.name}</span><small>{recent.path}</small>
              </button>
              <Button view="outlined" size="s" type="button" aria-label={`Forget ${recent.name}`} onClick={() => forgetRecentProject(recent.path)}>Forget</Button>
            </div>)}</div>
            {recentProjectError && <p className="error" role="alert">{recentProjectError}</p>}
            <p className="property-description">Stored only in this browser on this device. Opening uses the current read-only setting.</p>
          </section>}
          {backendStatus === "unavailable" && <div className="error" role="alert" data-testid="backend-unavailable">
            <strong>The RuFLEX backend is unavailable.</strong>
            <p>{backendHealthError ?? "Projects cannot be opened until the backend responds."}</p>
            <Button view="outlined" type="button" onClick={() => void checkBackendHealth()}>Retry backend connection</Button>
          </div>}
          {backendStatus === "checking" && <p role="status">Checking connection to the RuFLEX backend…</p>}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
        </section>
      ) : active === "DATA" ? (
        <section className="feature-workspace data-workspace">
          {project.read_only && <div className="info-message" role="status">Read-only project: saved data and evidence can be inspected, but dataset imports and contract changes are disabled. Close and reopen the project writable to make changes.</div>}
          {datasetStateStatus === "loading" && <div role="status">Checking for a persisted DatasetContract before enabling import or confirmation…</div>}
          {datasetStateStatus === "error" && <div className="error" role="alert"><strong>Could not verify persisted dataset state.</strong><p>{datasetStateError ?? "No empty-dataset state is inferred from this failure."}</p><Button view="outlined" onClick={() => setDatasetStateReload((current) => current + 1)}>Retry dataset check</Button></div>}
          {dataGovernanceObject && <section className="data-governance-inspector" aria-label="Selected data provenance object">
            <div className="evidence-check-header"><div><span className="eyebrow">OPENED FROM PROJECT LINEAGE</span><h3>{dataGovernanceObject.kind === "split_contract" ? "Frozen split membership" : dataGovernanceObject.kind === "transform_pipeline" ? "Train-only transform pipeline" : "Data leakage audit"}</h3></div>
              {dataGovernanceObject.kind === "leakage_audit" && <StatusBadge tone={dataGovernanceObject.value.status === "FAIL" ? "danger" : dataGovernanceObject.value.status === "WARN" ? "warning" : "success"}>{dataGovernanceObject.value.status}</StatusBadge>}
              {dataGovernanceObject.kind !== "leakage_audit" && <StatusBadge tone="success">FROZEN</StatusBadge>}
            </div>
            {dataGovernanceObject.kind === "split_contract" && <>
              <p>{dataGovernanceObject.value.family} split · seed {dataGovernanceObject.value.split_seed} · validation {Math.round(dataGovernanceObject.value.validation_fraction * 100)}% · test {Math.round(dataGovernanceObject.value.test_fraction * 100)}%</p>
              <div className="data-role-counts">{(["train", "validation", "test"] as const).map((role) => <div key={role}><span>{role === "test" ? "Locked test" : role}</span><strong>{dataGovernanceObject.value.role_source_rows[role].length} rows</strong><code>{dataGovernanceObject.value.role_identity_hashes[role].slice(0, 16)}…</code></div>)}</div>
              <p className="scientific-note">{dataGovernanceObject.value.scientific_note}</p>
            </>}
            {dataGovernanceObject.kind === "transform_pipeline" && <>
              <p>Fit role: <strong>{dataGovernanceObject.value.fit_role}</strong> · {dataGovernanceObject.value.feature_order.length} ordered features</p>
              <ol className="data-governance-steps">{dataGovernanceObject.value.steps.map((step, index) => <li key={`${step.step_type}-${index}`}><strong>{step.step_type}</strong> · fit on {step.fit_role} · {step.input_columns.join(", ")} → {step.output_columns.join(", ")}</li>)}</ol>
              <p>Preprocessing artifact SHA-256: <code>{dataGovernanceObject.value.preprocessing_artifact_sha256}</code></p>
              <p className="scientific-note">{dataGovernanceObject.value.scientific_note}</p>
            </>}
            {dataGovernanceObject.kind === "leakage_audit" && <>
              <p>{dataGovernanceObject.value.rigor_profile} · {dataGovernanceObject.value.findings.length} finding(s)</p>
              {dataGovernanceObject.value.findings.length ? <ul className="data-governance-findings">{dataGovernanceObject.value.findings.map((finding, index) => <li key={`${finding.code}-${index}`}><strong>{finding.severity.toUpperCase()} · {finding.code}</strong><span>{finding.remediation}</span></li>)}</ul> : <p>No structural findings were recorded.</p>}
              <p className="scientific-note">{dataGovernanceObject.value.scientific_note}</p>
            </>}
          </section>}
          <div className="data-layout">
            <div>
              {!dataset && datasetStateStatus === "none" && !pendingDatasetFile && <div className="info-message" role="status">This CSV is an editable draft only; inspect it and confirm the dataset contract to save it.</div>}
              {datasetStateStatus === "none" && !project.read_only && <div className="info-message" role="group" aria-label="Synthetic practice dataset">
                <p>The three-row editor example is for inspecting roles, not model training. For a first training run, load 80 deterministic synthetic practice rows or import your own dataset. Practice data is not research evidence.</p>
                <Button view="outlined" disabled={importingDatasetFile || confirmingCsvDataset} onClick={() => {
                  updateCsvText(SYNTHETIC_PRACTICE_CSV);
                  setTarget("target");
                  setTask("binary_classification");
                  setIdColumns("");
                  setExcludedColumns("");
                  setStatus("Synthetic practice draft loaded; inspect and confirm it before training");
                }}>Load synthetic practice CSV (80 rows)</Button>
                <p className="property-description">This replaces only the unsaved CSV editor draft. Confirming it creates a normal persisted DatasetContract; it never starts training or opens the final test.</p>
              </div>}
              <label className="field-label">
                CSV data
                <textarea
                  aria-label="CSV data"
                  value={csvText}
                  disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset}
                  onChange={(event) => updateCsvText(event.target.value)}
                  rows={8}
                />
              </label>
              <div className="contract-grid">
                <label className="field-label">
                  Target
                  {pendingDatasetProfile ? (
                    <select aria-label="Target" disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} value={target} onChange={(event) => event.target.value ? assignColumnRole(event.target.value, "target") : setTarget("")}>
                      <option value="">Select target column</option>
                      {pendingDatasetProfile.columns.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
                    </select>
                  ) : (
                    <TextInput aria-label="Target" value={target} onUpdate={setTarget} disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} />
                  )}
                </label>
                <label className="field-label">
                  Task
                  <select
                    aria-label="Task"
                    disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset}
                    value={task}
                    onChange={(event) => setTask(event.target.value)}
                  >
                    <option value="binary_classification">
                      Binary classification
                    </option>
                    <option value="regression">Regression</option>
                  </select>
                </label>
                <label className="field-label">
                  ID columns
                  <TextInput aria-label="ID columns" value={idColumns} onUpdate={setIdColumns} placeholder={profile?.id_candidates.join(", ") || "comma-separated, optional"} disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} />
                </label>
                <label className="field-label">
                  Exclude from model
                  <TextInput aria-label="Excluded feature columns" value={excludedColumns} onUpdate={setExcludedColumns} placeholder="column names, comma-separated" disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} />
                </label>
              </div>
              <p className="property-description">Excluded columns remain in the source dataset but are not passed to model fitting. Confirm the exact names before saving the contract.</p>
              <div className="form-actions">
                <Button view="outlined" disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} onClick={inspectCsv} data-ruflex-action="dataset.inspect">
                  Inspect dataset
                </Button>
                <Button
                  view="action"
                  disabled={!datasetStateResolved || !profile || !target.trim() || project.read_only || confirmingCsvDataset || importingDatasetFile}
                  onClick={confirmCsv}
                  data-ruflex-action="dataset.confirm"
                >
                  {confirmingCsvDataset ? "Saving dataset…" : "Confirm dataset contract"}
                </Button>
                <input
                  ref={datasetFileInputRef}
                  aria-label="Dataset CSV or XLSX file"
                  type="file"
                  accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  hidden
                  onChange={selectDatasetFile}
                />
                <Button
                  view="outlined"
                  disabled={!datasetStateResolved || project.read_only || inspectingDatasetFile || importingDatasetFile || confirmingCsvDataset}
                  onClick={() => datasetFileInputRef.current?.click()}
                  data-ruflex-action="dataset.import"
                >
                  {inspectingDatasetFile ? "Inspecting file…" : importingDatasetFile ? "Importing…" : "Import CSV / XLSX"}
                </Button>
                {pendingDatasetFile && (
                  <>
                    <span className="property-description" aria-live="polite">{inspectingDatasetFile ? `Inspecting ${pendingDatasetFile.name}…` : importingDatasetFile ? `Importing ${pendingDatasetFile.name}…` : `Selected: ${pendingDatasetFile.name} · target: ${target || "select from inspected columns"}`}</span>
                    <Button view="action" disabled={!pendingDatasetProfile || !target.trim() || project.read_only || inspectingDatasetFile || importingDatasetFile || confirmingCsvDataset} onClick={importDatasetFile} data-ruflex-action="dataset.import.confirm">
                      {importingDatasetFile ? "Saving file…" : "Confirm target and import file"}
                    </Button>
                  </>
                )}
              </div>
              {pendingDatasetProfile && (
                <div className="data-summary" aria-label="Selected file schema preview">
                  Candidate preview · {pendingDatasetFile?.name} · {pendingDatasetProfile.row_count} rows · {pendingDatasetProfile.columns.length} columns · not saved
                  <div className="data-table-wrap"><table className="data-table"><thead><tr><th>column</th><th>proposed role</th><th>confirmed role</th><th>type</th></tr></thead><tbody>{pendingDatasetProfile.columns.map((column) => <tr key={column.name}><td>{column.name}</td><td>{column.proposed_role}</td><td><select aria-label={`Role for ${column.name}`} value={columnRole(column.name)} disabled={!datasetStateResolved || project.read_only || importingDatasetFile || confirmingCsvDataset} onChange={(event) => assignColumnRole(column.name, event.target.value as "target" | "id" | "excluded" | "feature")}><option value="feature">Model feature</option><option value="target">Target</option><option value="id">ID</option><option value="excluded">Exclude from model</option></select></td><td>{column.semantic_type} · {column.dtype}</td></tr>)}</tbody></table></div>
                </div>
              )}
              {profile && !pendingDatasetFile && (
                <div className="data-summary">
                  Rows: {profile.row_count} · columns: {profile.columns.length}{" "}
                  · ID candidates: {profile.id_candidates.join(", ") || "none"}
                  <div className="info-message">Role proposals are advisory. Select each column's role here or edit the fields above; changes remain a draft until you confirm the DatasetContract.</div>
                  <div className="data-table-wrap"><table className="data-table"><thead><tr><th>column</th><th>proposal</th><th>confirmed role</th><th>confidence</th><th>reason</th></tr></thead><tbody>{profile.columns.map((column) => <tr key={column.name}><td>{column.name}</td><td>{column.proposed_role}</td><td><select aria-label={`Role for ${column.name}`} value={columnRole(column.name)} disabled={!datasetStateResolved || project.read_only || importingDatasetFile || confirmingCsvDataset} onChange={(event) => assignColumnRole(column.name, event.target.value as "target" | "id" | "excluded" | "feature")}><option value="feature">Model feature</option><option value="target">Target</option><option value="id">ID</option><option value="excluded">Exclude from model</option></select></td><td>{Math.round(column.role_confidence * 100)}%</td><td>{column.role_reason}</td></tr>)}</tbody></table></div>
                </div>
              )}
            </div>
            <aside className="data-health">
              <span className="eyebrow">DATASET HEALTH</span>
              {dataset ? (
                <>
                  <strong>
                    {dataset.audit.findings.length
                      ? `${dataset.audit.findings.length} findings`
                      : "No basic integrity findings"}
                  </strong>
                  {dataset.audit.findings.map((finding) => (
                    <div
                      key={`${finding.code}-${JSON.stringify(finding.evidence)}`}
                      className="audit-finding"
                    >
                      <span>{finding.code}</span>
                      <small>{finding.remediation}</small>
                    </div>
                  ))}
                </>
              ) : (
                <span>Inspect and confirm the dataset to create evidence.</span>
              )}
            </aside>
          </div>
          {dataset && (
            <div className="data-summary">
              Contract: {dataset.contract.target} · {dataset.contract.task}
              <small> · Row identity: {dataset.contract.row_identity_scheme}</small>
              <small> · Source: {dataset.contract.source_format.toUpperCase()} · SHA-256: <code>{dataset.contract.source_artifact_sha256}</code></small>
              {dataset.contract.source_artifact_sha256 === SYNTHETIC_PRACTICE_SHA256 && <p className="scientific-note" data-testid="synthetic-practice-provenance">These exact dataset bytes match the RuFLEX synthetic practice fixture. This is a training walkthrough, not benchmark or research evidence.</p>}
              <details aria-label="Frozen dataset roles">
                <summary>Confirmed roles · {dataset.contract.feature_columns.length} model features · {dataset.contract.id_columns.length} IDs · {dataset.contract.excluded_columns.length} other columns excluded</summary>
                <p><strong>Model features:</strong> {dataset.contract.feature_columns.join(", ") || "none"}</p>
                <p><strong>ID columns:</strong> {dataset.contract.id_columns.join(", ") || "none"}</p>
                <p><strong>Excluded from model:</strong> {dataset.contract.excluded_columns.join(", ") || "none"}</p>
              </details>
            </div>
          )}
          {datasetState && (
            <>
              <h2>Stored dataset preview</h2>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      {Object.keys(datasetState.preview[0] ?? {}).map(
                        (column) => (
                          <th key={column}>{column}</th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {datasetState.preview.slice(0, 12).map((row, index) => (
                      <tr key={index}>
                        {Object.keys(datasetState.preview[0] ?? {}).map(
                          (column) => (
                            <td key={column}>{String(row[column] ?? "∅")}</td>
                          ),
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {dataset && (
            <>
              <h2>What counts as new?</h2>
              {generalizationHydrationStatus === "loading" && <p role="status" data-testid="generalization-loading">Checking the saved GeneralizationContract… Scope-dependent review is paused until this read completes.</p>}
              {generalizationHydrationStatus === "none" && <p className="property-description" data-testid="generalization-empty">No saved GeneralizationContract exists for this project yet.</p>}
              {generalizationHydrationStatus === "error" && <div className="error" role="alert" data-testid="generalization-hydration-error"><strong>Saved GeneralizationContract could not be verified. Scope-dependent review is paused.</strong><p>{generalizationHydrationError}</p><Button view="outlined" onClick={() => setGeneralizationHydrationReload((current) => current + 1)}>Retry GeneralizationContract</Button></div>}
              <div className="contract-grid">
                <label className="field-label">
                  Intended use
                  <TextInput
                    aria-label="Intended use"
                    value={intendedUse}
                    disabled={generalizationMutationOperation !== null}
                    onUpdate={setIntendedUse}
                  />
                </label>
                <label className="field-label">
                  Novelty axis
                  <select
                    aria-label="Novelty axis"
                    value={noveltyAxis}
                    disabled={generalizationMutationOperation !== null}
                    onChange={(event) => setNoveltyAxis(event.target.value)}
                  >
                    <option value="entity">Entity</option>
                    <option value="time">Time</option>
                    <option value="site">Site</option>
                    <option value="device">Device</option>
                    <option value="regime">Regime</option>
                  </select>
                </label>
                <label className="field-label">
                  Scope field
                  <select
                    aria-label="Generalization scope field"
                    value={scopeField || datasetState?.contract.id_columns[0] || datasetState?.contract.feature_columns[0] || ""}
                    disabled={generalizationMutationOperation !== null}
                    onChange={(event) => setScopeField(event.target.value)}
                  >
                    {datasetState?.profile.columns.map((column) => (
                      <option value={column.name} key={column.name}>{column.name}</option>
                    ))}
                  </select>
                </label>
                <label className="field-label">
                  Candidate value to classify
                  <TextInput
                    aria-label="Generalization candidate value"
                    value={scopeCandidateValue}
                    disabled={generalizationMutationOperation !== null}
                    onUpdate={setScopeCandidateValue}
                    placeholder="north or external-lab"
                  />
                </label>
                <label className="field-label">
                  Supported values
                  <TextInput
                    aria-label="Supported scope values"
                    value={supportedScopeValues}
                    disabled={generalizationMutationOperation !== null}
                    onUpdate={setSupportedScopeValues}
                    placeholder="north, south"
                  />
                </label>
                <label className="field-label">
                  Forbidden values
                  <TextInput
                    aria-label="Forbidden scope values"
                    value={forbiddenScopeValues}
                    disabled={generalizationMutationOperation !== null}
                    onUpdate={setForbiddenScopeValues}
                    placeholder="external-lab"
                  />
                </label>
                <label className="field-label">
                  Outside declared supported scope
                  <select
                    aria-label="Unsupported scope action"
                    value={unsupportedAction}
                    disabled={generalizationMutationOperation !== null}
                    onChange={(event) => setUnsupportedAction(event.target.value as "BLOCK" | "REVIEW")}
                  >
                    <option value="BLOCK">Block</option>
                    <option value="REVIEW">Require review</option>
                  </select>
                </label>
              </div>
              <div className="form-actions">
                <Button
                  view="outlined"
                  disabled={project.read_only || generalizationHydrationStatus === "loading" || generalizationHydrationStatus === "error" || generalizationMutationOperation !== null || confirmingCsvDataset || importingDatasetFile}
                  onClick={createGeneralization}
                  data-ruflex-action="generalization.declare"
                >
                  {generalizationMutationOperation === "declare" ? "Declaring…" : "Declare generalization contract"}
                </Button>
                <Button
                  view="action"
                  disabled={
                    project.read_only ||
                    generalizationMutationOperation !== null ||
                    confirmingCsvDataset ||
                    importingDatasetFile ||
                    generalizationHydrationStatus !== "available" ||
                    !generalization?.lint.can_freeze ||
                    !!generalization.contract.frozen_at
                  }
                  onClick={freezeGeneralization}
                  data-ruflex-action="generalization.freeze"
                >
                  {generalizationMutationOperation === "freeze" ? "Freezing…" : "Freeze evaluation contract"}
                </Button>
              </div>
              {generalization && (
                <div className="generalization-contract-card">
                  <div className="artifact-details">
                    Split recommendation:{" "}
                    {generalization.recommendations
                      .map((item) => item.family)
                      .join(", ")}{" "}
                    ·{" "}
                    {generalization.contract.frozen_at
                      ? "Frozen"
                      : generalization.lint.can_freeze
                        ? "Ready to freeze"
                        : generalization.lint.findings
                            .map((item) => item.code)
                            .join(", ")}
                  </div>
                  <div className="generalization-scope-grid">
                    <div>
                      <span className="eyebrow">SUPPORTED SCOPE</span>
                      {generalization.contract.supported_scope.length
                        ? generalization.contract.supported_scope.map((rule, index) => <p key={`supported-${index}`}><code>{rule.field} {rule.operator} {JSON.stringify(rule.value)}</code><br /><small>{rule.rationale}</small></p>)
                        : <p><StatusBadge tone="warning">not explicitly bounded</StatusBadge> <small>No supported-scope rule was declared; this contract must not be read as evidence of unrestricted generalization.</small></p>}
                    </div>
                    <div>
                      <span className="eyebrow">FORBIDDEN / OUTSIDE SCOPE</span>
                      {generalization.contract.forbidden_scope.length
                        ? generalization.contract.forbidden_scope.map((rule, index) => <p key={`forbidden-${index}`}><code>{rule.field} {rule.operator} {JSON.stringify(rule.value)}</code><br /><small>{rule.rationale}</small></p>)
                        : <p><small>No explicit forbidden-value rule.</small></p>}
                      <p><strong>Outside supported scope: {generalization.contract.unsupported_action}</strong></p>
                    </div>
                  </div>
                  <div className="form-actions">
                    <Button view="outlined" disabled={generalizationHydrationStatus !== "available" || !datasetState?.preview.length} onClick={() => checkScope("preview")}>Check first preview row</Button>
                    <Button view="outlined" disabled={generalizationHydrationStatus !== "available" || !datasetState?.preview.length || !scopeCandidateValue.trim()} onClick={() => checkScope("candidate")}>Check candidate scope</Button>
                    {scopeClassification && <StatusBadge tone={scopeClassification.disposition === "ALLOW" ? "success" : scopeClassification.disposition === "BLOCK" ? "danger" : "warning"}>{scopeClassification.disposition}</StatusBadge>}
                  </div>
                  {scopeClassification && <p className="property-description">{scopeClassification.reasons.join(" ")}</p>}
                </div>
              )}
            </>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
        </section>
      ) : active === "MODELS" ? (
        <BuildWorkspace
          project={project}
          dataset={datasetState}
          evaluation={fisEvaluation}
          evaluationStatus={fisEvaluationStatus}
          evaluationError={fisEvaluationError}
          onRetryEvaluation={() => setFisEvaluationReload((current) => current + 1)}
          theme={theme}
          fis={fis}
          modelContextStatus={overviewContextSessionId === project.session_id ? overviewContextStatus : "loading"}
          modelContextError={overviewContextError}
          onRetryModelContext={() => setOverviewContextReload((current) => current + 1)}
          sourceExplanationId={explanation?.explanation_id ?? null}
          selectedExpertCorrectionId={selectedExpertCorrectionId}
          onExpertCorrection={bindProjectSession(project.session_id, setExpertCorrection)}
          onFisChange={bindProjectSession(project.session_id, setFis)}
          onEvaluation={bindProjectSession(project.session_id, (evaluation) => {
            setPreviousFisEvaluation(fisEvaluation);
            setFisEvaluation(evaluation);
            setFisEvaluationStatus("available");
            setFisEvaluationError(null);
            void refreshArtifactInventory(project.session_id);
          })}
          onOpenTrace={() => setActive("EVIDENCE")}
        />
      ) : active === "STUDIES" ? (
        <ExperimentWorkspace
          project={project}
          dataset={datasetState}
          datasetHydrationStatus={datasetStateStatus}
          datasetHydrationError={datasetStateError}
          onRetryDatasetHydration={() => setDatasetStateReload((current) => current + 1)}
          run={trainingRun}
          study={trainingStudy}
          studyHydrationStatus={trainingStudyStatus}
          studyHydrationError={trainingStudyError}
          onRetryStudyHydration={() => setTrainingStudyReload((current) => current + 1)}
          theme={theme}
          onRun={bindProjectSession(project.session_id, (run) => {
            setTrainingRun(run);
            setTrainingRunsReload((current) => current + 1);
            setStatus(`Training run ${run.run_id.slice(0, 8)} completed`);
            void refreshArtifactInventory(project.session_id);
          })}
          onStudy={bindProjectSession(project.session_id, (study) => { setTrainingStudy(study); setTrainingStudyStatus("available"); setTrainingStudyError(null); })}
          onStabilityAnalysisChange={bindProjectSession(project.session_id, handleStabilityAnalysisChange)}
          onStabilityGatePolicyChange={bindProjectSession(project.session_id, setStabilityGatePolicy)}
        />
      ) : active === "ANALYSES" ? (
        <EvaluationWorkspace key={project.session_id} project={project} dataset={datasetState} datasetHydrationStatus={datasetStateStatus} datasetHydrationError={datasetStateError} onRetryDatasetHydration={() => setDatasetStateReload((current) => current + 1)} fis={fis} modelContextStatus={overviewContextSessionId === project.session_id ? overviewContextStatus : "loading"} modelContextError={overviewContextError} onRetryModelContext={() => setOverviewContextReload((current) => current + 1)} run={trainingRun} runs={trainingRuns} runListStatus={trainingRunsStatus} runListError={trainingRunsError} onRetryRunList={() => setTrainingRunsReload((current) => current + 1)} study={trainingStudy} evaluation={analysisEvaluation} evaluationStatus={analysisEvaluationStatus} evaluationError={analysisEvaluationError} onRetryEvaluation={() => setAnalysisEvaluationReload((current) => current + 1)} validationPolicyEvidenceStatus={validationPolicyEvidenceStatus} validationPolicyEvidenceError={validationPolicyEvidenceError} onRetryValidationPolicyEvidence={() => setValidationPolicyEvidenceReload((current) => current + 1)} calibrationTransform={calibrationTransform} decisionThreshold={decisionThreshold} finalTestEvaluation={finalTestEvaluation} finalTestEvidenceStatus={finalTestEvidenceStatus} finalTestEvidenceError={finalTestEvidenceError} onRetryFinalTestEvidence={() => setFinalTestEvidenceReload((current) => current + 1)} comparison={analysisComparison} comparisonHydrationStatus={analysisComparisonHydrationStatus} comparisonHydrationError={analysisComparisonHydrationError} onRetryComparison={() => setAnalysisComparisonHydrationReload((current) => current + 1)} sliceAnalysis={sliceAnalysis} sliceAnalysisHydrationStatus={sliceAnalysisHydrationStatus} sliceAnalysisHydrationError={sliceAnalysisHydrationError} onRetrySliceAnalysis={() => setSliceAnalysisHydrationReload((current) => current + 1)} selectivePolicy={selectivePolicy} stabilityGatePolicy={stabilityGatePolicy} theme={theme} onEvaluation={bindProjectSession(project.session_id, (evaluation) => { setAnalysisEvaluation(evaluation); setAnalysisEvaluationStatus("available"); })} onCalibration={bindProjectSession(project.session_id, setCalibrationTransform)} onThreshold={bindProjectSession(project.session_id, setDecisionThreshold)} onSelectivePolicy={bindProjectSession(project.session_id, setSelectivePolicy)} onFinalTest={bindProjectSession(project.session_id, (evaluation) => { setFinalTestEvaluation(evaluation); if (evaluation) setFinalTestEvidenceStatus("available"); })} onComparison={bindProjectSession(project.session_id, (comparison) => { setAnalysisComparison(comparison); setAnalysisComparisonHydrationStatus("available"); setAnalysisComparisonHydrationError(null); })} onSliceAnalysis={bindProjectSession(project.session_id, (analysis) => { setSliceAnalysis(analysis); setSliceAnalysisHydrationStatus("available"); setSliceAnalysisHydrationError(null); })} />
      ) : active === "EVIDENCE" ? (
        <EvidenceWorkspace
          project={project}
          dataset={datasetState}
          fis={fis}
          modelContextStatus={overviewContextSessionId === project.session_id ? overviewContextStatus : "loading"}
          modelContextError={overviewContextError}
          onRetryModelContext={() => setOverviewContextReload((current) => current + 1)}
          run={trainingRun}
          evaluation={fisEvaluation}
          previousEvaluation={previousFisEvaluation}
          treeEvidence={treeEvidence}
          treeEvidenceHydrationStatus={treeEvidenceHydrationStatus}
          treeEvidenceHydrationError={treeEvidenceHydrationError}
          onRetryTreeEvidence={() => setTreeEvidenceHydrationReload((current) => current + 1)}
          explanation={explanation}
          explanationHydrationStatus={explanationHydrationStatus}
          explanationHydrationError={explanationHydrationError}
          onRetryExplanation={() => setExplanationHydrationReload((current) => current + 1)}
          explanationCheck={explanationCheck}
          explanationCheckHydrationStatus={explanationCheckHydrationStatus}
          explanationCheckHydrationError={explanationCheckHydrationError}
          onRetryExplanationCheck={() => setExplanationCheckHydrationReload((current) => current + 1)}
          behaviorResult={behaviorResult}
          behaviorSpec={behaviorSpec}
          behaviorSpecResultStatus={behaviorSpecResultStatus}
          behaviorSpecResultError={behaviorSpecResultError}
          onRetryBehaviorSpecResult={() => setBehaviorSpecResultReload((current) => current + 1)}
          lineageBehaviorComparison={lineageBehaviorComparison}
          reproducibility={reproducibility}
          reproducibilityHydrationStatus={reproducibilityHydrationStatus}
          reproducibilityHydrationError={reproducibilityHydrationError}
          onRetryReproducibility={() => setReproducibilityHydrationReload((current) => current + 1)}
          exhaustive={exhaustive}
          exhaustiveHydrationStatus={exhaustiveHydrationStatus}
          exhaustiveHydrationError={exhaustiveHydrationError}
          onRetryExhaustive={() => setExhaustiveHydrationReload((current) => current + 1)}
          assurance={assurance}
          verificationBundleRecord={verificationBundleRecord}
          assuranceHydrationStatus={assuranceHydrationStatus}
          assuranceHydrationError={assuranceHydrationError}
          onRetryAssurance={() => setAssuranceHydrationReload((current) => current + 1)}
          selectivePolicy={selectivePolicy}
          generalization={generalization}
          generalizationHydrationStatus={generalizationHydrationStatus}
          generalizationHydrationError={generalizationHydrationError}
          onRetryGeneralization={() => setGeneralizationHydrationReload((current) => current + 1)}
          theme={theme}
          onExplanation={bindProjectSession(project.session_id, (value) => {
            setExplanation(value);
            setExplanationHydrationStatus(value ? "available" : "none");
            setExplanationHydrationError(null);
          })}
          onExplanationCheck={bindProjectSession(project.session_id, (value) => {
            setExplanationCheck(value);
            setExplanationCheckHydrationStatus(value ? "available" : "none");
            setExplanationCheckHydrationError(null);
          })}
          onBehaviorResult={bindProjectSession(project.session_id, (result) => {
            setBehaviorResult(result);
            setBehaviorSpecResultStatus(result ? "available" : "none");
            setBehaviorSpecResultError(null);
          })}
          onReproducibility={bindProjectSession(project.session_id, (value) => {
            setReproducibility(value);
            setReproducibilityHydrationStatus(value ? "available" : "none");
            setReproducibilityHydrationError(null);
          })}
          onExhaustive={bindProjectSession(project.session_id, (value) => {
            setExhaustive(value);
            setExhaustiveHydrationStatus(value ? "available" : "none");
            setExhaustiveHydrationError(null);
          })}
          onAssurance={bindProjectSession(project.session_id, (value) => {
            setAssurance(value);
            setAssuranceHydrationStatus(value ? "available" : "none");
            setAssuranceHydrationError(null);
          })}
        />
      ) : (
        <section className="foundation-workspace">
            <div className="feature-toolbar">
            <div>
              <span className="eyebrow">PROJECT OVERVIEW</span>
              <h2>Scientific objects, not a required pipeline</h2>
              <p>
                Select Data, Models, Studies, Analyses or Evidence from the
                Project Explorer.
              </p>
            </div>
            </div>
          {overviewContextStatus === "loading" && <div role="status">Checking saved model and training context before showing project next steps…</div>}
          {overviewContextStatus === "error" && <div className="error" role="alert"><strong>Could not verify saved model or training context.</strong><p>{overviewContextError ?? "The project is not assumed to be empty after a failed read."}</p><Button view="outlined" onClick={() => setOverviewContextReload((current) => current + 1)}>Retry project context check</Button></div>}
          {integrityStatus === "loading" && <div role="status">Checking persisted project integrity…</div>}
          {integrityStatus === "error" && <div className="error" role="alert"><strong>Project integrity is unavailable.</strong><p>{integrityError ?? "Persisted project evidence has not been verified."}</p><Button view="outlined" onClick={() => setIntegrityReload((current) => current + 1)}>Retry integrity check</Button></div>}
          {integrityStatus === "available" && integrity && <div className="trace-card" data-testid="project-integrity"><div className="evidence-check-header"><strong>Reopen integrity</strong><StatusBadge tone={integrity.status === "PASS" ? "success" : integrity.status === "FAIL" ? "danger" : "warning"}>{integrity.status}</StatusBadge></div><p>{integrity.checked_objects} persisted objects checked. {integrity.scientific_note}</p>{integrity.issues.map((issue) => <p className="property-description" key={`${issue.code}-${issue.path}`}>{issue.code} · {issue.path} · {issue.detail}</p>)}</div>}
          {overviewContextStatus === "loaded" && datasetStateStatus === "none" && !fis && !trainingRun && (
            <section className="quick-start-card" aria-label="Optional quick start">
              <div>
                <span className="eyebrow">OPTIONAL QUICK START</span>
                <h2>Start with your data</h2>
                <p>Inspect a CSV or Excel file, choose its target and task, then confirm a DatasetContract. This shortcut only opens the Data workspace; it does not start training or access the locked test split.</p>
              </div>
              <Button view="action" onClick={() => setActive("DATA")} data-ruflex-action="project.quickstart.data">Review or import data</Button>
            </section>
          )}
          {overviewContextStatus === "loaded" && datasetStateStatus === "available" && datasetState && !trainingRun && (
            <section className="quick-start-card" aria-label="Optional next step">
              {projectStudyNextStep({ status: trainingStudyStatus, hasStudy: Boolean(trainingStudy), hasTrainingRun: Boolean(trainingRun) }) === "TRAIN" && <>
              <div>
                <span className="eyebrow">OPTIONAL NEXT STEP</span>
                <h2>Your dataset is ready for a model fit</h2>
                <p>Open Training to review the model and split settings. Nothing runs until you choose “Run real training”; the held-out test split stays locked.</p>
              </div>
              <Button view="action" onClick={() => setActive("STUDIES")} data-ruflex-action="project.quickstart.training">Open Training</Button>
              </>}
              {projectStudyNextStep({ status: trainingStudyStatus, hasStudy: Boolean(trainingStudy), hasTrainingRun: Boolean(trainingRun) }) === "OPEN_SAVED_STUDY" && <>
                <div>
                  <span className="eyebrow">SAVED WORK</span>
                  <h2>Your TrainingStudy is ready to inspect</h2>
                  <p>{trainingStudy?.name} · {trainingStudy?.seed_runs.length} persisted runs. Open the study to review its selected run and validation evidence; no new fit is started.</p>
                </div>
                <Button view="action" onClick={() => setActive("STUDIES")} data-ruflex-action="project.quickstart.study">Open saved study</Button>
              </>}
              {projectStudyNextStep({ status: trainingStudyStatus, hasStudy: Boolean(trainingStudy), hasTrainingRun: Boolean(trainingRun) }) === "CHECKING" && <p role="status">Checking saved study history before suggesting a next step…</p>}
              {projectStudyNextStep({ status: trainingStudyStatus, hasStudy: Boolean(trainingStudy), hasTrainingRun: Boolean(trainingRun) }) === "UNAVAILABLE" && <div role="alert"><strong>Saved study history could not be verified, so no training next step is suggested.</strong><p>{trainingStudyError}</p><Button view="outlined" onClick={() => setTrainingStudyReload((current) => current + 1)}>Retry study history</Button></div>}
            </section>
          )}
          <div className="project-overview-grid">
            <button onClick={() => setActive("DATA")}>
              Data
              <br />
              <small>
                {datasetState
                  ? `${datasetState.profile.row_count} rows`
                  : datasetStateStatus === "loading" || datasetStateStatus === "idle" ? "Checking dataset…" : datasetStateStatus === "error" ? "Dataset state unavailable" : "No dataset"}
              </small>
            </button>
            <button onClick={() => setActive("MODELS")}>
              Models
              <br />
              <small>{projectModelOverviewLabel({
                status: overviewContextStatus,
                fisName: fis?.name ?? null,
                trainingModelKind: trainingRun?.model_kind ?? null,
              })}</small>
            </button>
            <button onClick={() => setActive("STUDIES")}>
              Studies
              <br />
              <small>
                {trainingStudyOverviewLabel({
                  status: trainingStudyStatus,
                  studyName: trainingStudy?.name ?? null,
                  runCount: trainingStudy?.seed_runs.length ?? null,
                  hasTrainingRun: Boolean(trainingRun),
                })}
              </small>
            </button>
            <button onClick={() => setActive("ANALYSES")}>
              Analyses
              <br />
              <small>
                {analysisOverviewLabel({
                  hasValidationEvaluation: Boolean(analysisEvaluation),
                  hasTrainingRun: Boolean(trainingRun),
                })}
              </small>
            </button>
            <button onClick={() => setActive("EVIDENCE")}>
              Evidence
              <br />
              <small>
                {evidenceOverviewLabel(Boolean(fisEvaluation))}
              </small>
            </button>
          </div>
          <div className="project-lineage-panel">
            <div>
              <span className="eyebrow">PROJECT LINEAGE</span>
              <h3>Persisted provenance graph</h3>
              <p>Edges come only from saved object references; the graph is not a required execution order.</p>
            </div>
            <ProjectLineage
              graph={lineage}
              status={lineageStatus}
              error={lineageError}
              objectError={lineageObjectError}
              onRetryObject={() => { if (lineageRetryNode) void openLineageNode(lineageRetryNode); }}
              onRetry={() => setLineageReload((current) => current + 1)}
              onOpen={openLineageNode}
            />
          </div>
        </section>
      )}
    </AppShell>
  );
}
