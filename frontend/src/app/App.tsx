import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
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
type DataGovernanceObject =
  | { kind: "split_contract"; value: SplitContract }
  | { kind: "transform_pipeline"; value: TransformPipelineContract }
  | { kind: "leakage_audit"; value: LeakageAuditReport };
const initialTheme =
  (localStorage.getItem("ruflex.theme") as StudioTheme | null) ?? "light";

export function App() {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [readOnly, setReadOnly] = useState(false);
  const [status, setStatus] = useState("Connecting to backend…");
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<StudioTheme>(initialTheme);
  const [active, setActive] = useState("PROJECT");
  const [collapsed, setCollapsed] = useState<Record<Panels, boolean>>({
    explorer: false,
    inspector: false,
    bottom: false,
  });
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
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
  const [intendedUse, setIntendedUse] = useState("New entities");
  const [noveltyAxis, setNoveltyAxis] = useState("entity");
  const [generalization, setGeneralization] =
    useState<GeneralizationResponse | null>(null);
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
  const [stabilityGatePolicy, setStabilityGatePolicy] = useState<StabilityGatePolicy | null>(null);
  const [analysisEvaluation, setAnalysisEvaluation] = useState<AnalysisEvaluation | null>(null);
  const [analysisEvaluationStatus, setAnalysisEvaluationStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [analysisEvaluationError, setAnalysisEvaluationError] = useState<string | null>(null);
  const [analysisEvaluationReload, setAnalysisEvaluationReload] = useState(0);
  const [validationPolicyEvidenceStatus, setValidationPolicyEvidenceStatus] = useState<"idle" | "loading" | "available" | "error">("idle");
  const [validationPolicyEvidenceError, setValidationPolicyEvidenceError] = useState<string | null>(null);
  const [validationPolicyEvidenceReload, setValidationPolicyEvidenceReload] = useState(0);
  const [analysisComparison, setAnalysisComparison] = useState<AnalysisComparison | null>(null);
  const [calibrationTransform, setCalibrationTransform] = useState<CalibrationTransform | null>(null);
  const [decisionThreshold, setDecisionThreshold] = useState<DecisionThresholdPolicy | null>(null);
  const [finalTestEvaluation, setFinalTestEvaluation] = useState<FinalTestEvaluation | null>(null);
  const [finalTestEvidenceStatus, setFinalTestEvidenceStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [finalTestEvidenceError, setFinalTestEvidenceError] = useState<string | null>(null);
  const [finalTestEvidenceReload, setFinalTestEvidenceReload] = useState(0);
  const [sliceAnalysis, setSliceAnalysis] = useState<SliceAnalysis | null>(null);
  const [treeEvidence, setTreeEvidence] = useState<TreePathEvidence | null>(null);
  const [explanation, setExplanation] = useState<ExplanationContract | null>(null);
  const [explanationCheck, setExplanationCheck] = useState<ExplanationCheck | null>(null);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorSpecResult | null>(null);
  const [behaviorSpec, setBehaviorSpec] = useState<BehaviorSpec | null>(null);
  const [behaviorSpecResultStatus, setBehaviorSpecResultStatus] = useState<"idle" | "loading" | "none" | "available" | "error">("idle");
  const [behaviorSpecResultError, setBehaviorSpecResultError] = useState<string | null>(null);
  const [behaviorSpecResultReload, setBehaviorSpecResultReload] = useState(0);
  const [lineageBehaviorComparison, setLineageBehaviorComparison] = useState<BehaviorRevisionComparison | null>(null);
  const [selectivePolicy, setSelectivePolicy] = useState<SelectivePredictionPolicy | null>(null);
  const [reproducibility, setReproducibility] = useState<ExplanationReproducibilityAnalysis | null>(null);
  const [exhaustive, setExhaustive] = useState<ExhaustiveLabResult | null>(null);
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
  const [dataGovernanceObject, setDataGovernanceObject] = useState<DataGovernanceObject | null>(null);
  const [integrity, setIntegrity] = useState<ProjectIntegrityReport | null>(null);
  const [integrityStatus, setIntegrityStatus] = useState<"idle" | "loading" | "available" | "error">("idle");
  const [integrityError, setIntegrityError] = useState<string | null>(null);
  const [integrityReload, setIntegrityReload] = useState(0);
  const [selectedExpertCorrectionId, setSelectedExpertCorrectionId] = useState<string | null>(null);
  const datasetFileInputRef = useRef<HTMLInputElement>(null);
  const datasetFileSelectionId = useRef(0);
  useEffect(() => {
    studioApi
      .health()
      .then(() => setStatus("Backend connected"))
      .catch((reason: Error) => {
        setError(reason.message);
        setStatus("Backend unavailable");
      });
  }, []);
  useEffect(() => {
    if (project)
      studioApi
        .listArtifacts(project.session_id)
        .then(setArtifacts)
        .catch((reason: Error) => setError(reason.message));
    else setArtifacts([]);
  }, [project?.session_id]);
  useEffect(() => {
    let active = true;
    if (!project) {
      setDatasetState(null);
      setDataset(null);
      setProfile(null);
      setDatasetStateStatus("idle");
      setDatasetStateError(null);
      setOverviewContextStatus("idle");
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
      setStabilityGatePolicy(null);
      setAnalysisEvaluation(null);
      setAnalysisEvaluationStatus("idle");
      setAnalysisEvaluationError(null);
      setValidationPolicyEvidenceStatus("idle");
      setValidationPolicyEvidenceError(null);
      setAnalysisComparison(null);
      setCalibrationTransform(null);
      setDecisionThreshold(null);
      setFinalTestEvaluation(null);
      setFinalTestEvidenceStatus("idle");
      setFinalTestEvidenceError(null);
      setSliceAnalysis(null);
      setTreeEvidence(null);
      setExplanation(null);
      setExplanationCheck(null);
      setBehaviorSpec(null);
      setBehaviorResult(null);
      setBehaviorSpecResultStatus("idle");
      setBehaviorSpecResultError(null);
      setLineageBehaviorComparison(null);
      setSelectivePolicy(null);
      setReproducibility(null);
      setExhaustive(null);
      setAssurance(null);
      setAssuranceHydrationStatus("idle");
      setAssuranceHydrationError(null);
      setVerificationBundleRecord(null);
      setExpertCorrection(null);
      setGeneralization(null);
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
    setOverviewContextStatus("loading");
    setOverviewContextError(null);
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
    setStabilityAnalysis(null);
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
      setFis(fisResult.kind === "value" ? fisResult.value : null);
      setTrainingRun(runResult.kind === "value" ? runResult.value : null);
      const failures = [fisResult, runResult].filter((result) => result.kind === "error");
      if (failures.length) {
        const first = failures[0];
        setOverviewContextStatus("error");
        setOverviewContextError(first.kind === "error" && first.reason instanceof Error ? first.reason.message : "Saved project model/training context could not be verified.");
      } else {
        setOverviewContextStatus("loaded");
      }
    });
    studioApi.listStudyStabilityAnalyses(project.session_id).then((items) => setStabilityAnalysis(items.at(-1) ?? null)).catch(() => setStabilityAnalysis(null));
    studioApi
      .getLatestAnalysisComparison(project.session_id)
      .then(setAnalysisComparison)
      .catch(() => setAnalysisComparison(null));
    studioApi.getLatestSliceAnalysis(project.session_id).then(setSliceAnalysis).catch(() => setSliceAnalysis(null));
    studioApi.getLatestTreePath(project.session_id).then(setTreeEvidence).catch(() => setTreeEvidence(null));
    studioApi.getLatestExplanation(project.session_id).then(setExplanation).catch(() => setExplanation(null));
    studioApi.getLatestExplanationCheck(project.session_id).then(setExplanationCheck).catch(() => setExplanationCheck(null));
    studioApi.getLatestExplanationReproducibility(project.session_id).then(setReproducibility).catch(() => setReproducibility(null));
    studioApi.getLatestExhaustiveLab(project.session_id).then(setExhaustive).catch(() => setExhaustive(null));
    studioApi.getLatestExpertCorrection(project.session_id).then(setExpertCorrection).catch(() => setExpertCorrection(null));
    studioApi.getActiveGeneralization(project.session_id).then(setGeneralization).catch(() => setGeneralization(null));
    return () => { active = false; };
  }, [project?.session_id, overviewContextReload]);
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
      setDatasetState(state);
      setProfile(state.profile);
      setDataset({ contract: state.contract, audit: state.audit });
      setTarget(state.contract.target);
      setTask(state.contract.task);
      setIdColumns(state.contract.id_columns.join(", "));
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
    const objectId = node.object_id;
    setLineageObjectError(null);
    setLineageRetryNode(null);
    try {
      if (node.kind === "training_run" && objectId) {
        setTrainingRun(await studioApi.getTrainingRun(project.session_id, objectId));
      } else if (node.kind === "fis" && objectId) {
        const revisions = await studioApi.getFisRevisions(project.session_id);
        const spec = revisions.find((candidate) => candidate.fis_id === objectId);
        if (!spec) throw new Error(`FIS is no longer available: ${objectId}`);
        setFis(spec);
      } else if (node.kind === "fis_revision") {
        const semanticHash = node.id.split(":").at(-1);
        const revisions = await studioApi.getFisRevisions(project.session_id);
        const revision = revisions.find((candidate) => candidate.semantic_hash === semanticHash);
        if (!revision) throw new Error(`FIS revision is no longer available: ${semanticHash ?? node.id}`);
        setFis(revision);
      } else if (node.kind === "study" && objectId) {
        setTrainingStudy(await studioApi.getTrainingStudy(project.session_id, objectId));
        setTrainingStudyStatus("available");
      } else if (node.kind === "study_stability" && objectId) {
        setStabilityAnalysis(await studioApi.getStudyStabilityAnalysis(project.session_id, objectId));
      } else if (node.kind === "evaluation" && objectId) {
        setAnalysisEvaluation(await studioApi.getAnalysisEvaluation(project.session_id, objectId));
        setAnalysisEvaluationStatus("available");
      } else if (node.kind === "calibration" && objectId) {
        setCalibrationTransform(await studioApi.getAnalysisCalibration(project.session_id, objectId));
      } else if (node.kind === "decision_threshold" && objectId) {
        setDecisionThreshold(await studioApi.getAnalysisThreshold(project.session_id, objectId));
      } else if (node.kind === "stability_gate_policy" && objectId) {
        setStabilityGatePolicy(await studioApi.getStabilityGatePolicy(project.session_id, objectId));
      } else if (node.kind === "selective_policy" && objectId) {
        setSelectivePolicy(await studioApi.getSelectivePolicy(project.session_id, objectId));
      } else if (node.kind === "final_test_evaluation" && objectId) {
        setFinalTestEvaluation(await studioApi.getFinalTestEvaluation(project.session_id, objectId));
        setFinalTestEvidenceStatus("available");
      } else if (node.kind === "comparison" && objectId) {
        setAnalysisComparison(await studioApi.getAnalysisComparison(project.session_id, objectId));
      } else if (node.kind === "slice_analysis" && objectId) {
        setSliceAnalysis(await studioApi.getSliceAnalysis(project.session_id, objectId));
      } else if (node.kind === "tree_path" && objectId) {
        setTreeEvidence(await studioApi.getTreePath(project.session_id, objectId));
      } else if (node.kind === "explanation" && objectId) {
        setExplanation(await studioApi.getExplanation(project.session_id, objectId));
      } else if (node.kind === "explanation_check" && objectId) {
        setExplanationCheck(await studioApi.getExplanationCheck(project.session_id, objectId));
      } else if (node.kind === "generalization_contract" && objectId) {
        setGeneralization(await studioApi.getGeneralization(project.session_id, objectId));
        setScopeClassification(null);
      } else if (node.kind === "expert_correction" && objectId) {
        const correction = await studioApi.getExpertCorrection(project.session_id, objectId);
        const revisions = await studioApi.getFisRevisions(project.session_id);
        const resultRevision = revisions.find((revision) => revision.semantic_hash === correction.result_semantic_hash);
        if (resultRevision) setFis(resultRevision);
        setExpertCorrection(correction);
        setSelectedExpertCorrectionId(objectId);
      } else if (node.kind === "split_contract" && objectId) {
        setDataGovernanceObject({ kind: "split_contract", value: await studioApi.getSplitContract(project.session_id, objectId) });
      } else if (node.kind === "transform_pipeline" && objectId) {
        setDataGovernanceObject({ kind: "transform_pipeline", value: await studioApi.getTransformPipeline(project.session_id, objectId) });
      } else if (node.kind === "leakage_audit" && objectId) {
        setDataGovernanceObject({ kind: "leakage_audit", value: await studioApi.getLeakageAudit(project.session_id, objectId) });
      } else if (node.kind === "behavior_spec" && objectId) {
        const specs = await studioApi.listBehaviorSpecs(project.session_id);
        const spec = specs.find((candidate) => candidate.spec_id === objectId);
        if (!spec) throw new Error(`BehaviorSpec is no longer available: ${objectId}`);
        setBehaviorSpec(spec);
        setBehaviorResult(null);
      } else if (node.kind === "behavior_spec_result" && objectId) {
        const results = await studioApi.listBehaviorResults(project.session_id);
        const result = results.find((candidate) => candidate.result_id === objectId);
        if (!result) throw new Error(`BehaviorSpecResult is no longer available: ${objectId}`);
        const specs = await studioApi.listBehaviorSpecs(project.session_id);
        const spec = specs.find((candidate) => candidate.spec_id === result.spec_id);
        if (!spec) throw new Error(`BehaviorSpec ${result.spec_id} for this result is no longer available`);
        setBehaviorSpec(spec);
        setBehaviorResult(result);
      } else if (node.kind === "behavior_revision_comparison" && objectId) {
        const comparisons = await studioApi.listBehaviorRevisionComparisons(project.session_id);
        const comparison = comparisons.find((candidate) => candidate.comparison_id === objectId);
        if (!comparison) throw new Error(`Behavior revision comparison is no longer available: ${objectId}`);
        setLineageBehaviorComparison(comparison);
      } else if (node.kind === "assurance_case" && objectId) {
        setAssurance(await studioApi.getAssuranceCase(project.session_id, objectId));
        setAssuranceHydrationStatus("available");
        setAssuranceHydrationError(null);
      } else if (node.kind === "verification_bundle" && objectId) {
        setVerificationBundleRecord(await studioApi.getVerificationBundle(project.session_id, objectId));
      } else if (node.kind === "explanation_reproducibility" && objectId) {
        setReproducibility(await studioApi.getExplanationReproducibility(project.session_id, objectId));
      } else if (node.kind === "exhaustive_lab" && objectId) {
        setExhaustive(await studioApi.getExhaustiveLabResult(project.session_id, objectId));
      } else if (node.kind === "dataset") {
        setDataGovernanceObject(null);
      }
      setActive(node.target);
      setStatus(`Opened lineage object: ${node.label}`);
    } catch (reason) {
      setLineageRetryNode(node);
      setLineageObjectError(reason instanceof Error ? reason.message : "Could not open the selected persisted object.");
      setError(reason instanceof Error ? reason.message : "Could not open lineage object");
    }
  }
  const toggle = (panel: Panels) =>
    setCollapsed((current) => ({ ...current, [panel]: !current[panel] }));
  async function submit(event: FormEvent, operation: "create" | "open") {
    event.preventDefault();
    setError(null);
    try {
      const result =
        operation === "create"
          ? await studioApi.createProject(path, name)
          : await studioApi.openProject(path, readOnly);
      setProject(result);
      setDescription(result.description ?? "");
      setStatus(
        `${operation === "create" ? "Created" : "Opened"} ${result.name}`,
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unknown request failure",
      );
    }
  }
  async function save() {
    if (!project) return;
    setError(null);
    try {
      const result = await studioApi.saveProject(project.session_id);
      setProject(result);
      setStatus(`Saved ${result.name}`);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unknown request failure",
      );
    }
  }
  async function updateDescription() {
    if (!project || project.read_only) return;
    try {
      const result = await studioApi.updateProjectMetadata(
        project.session_id,
        description,
      );
      setProject(result);
      setStatus(`Updated ${result.name}`);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unknown request failure",
      );
    }
  }
  async function close() {
    datasetFileSelectionId.current += 1;
    if (project) {
      try {
        await studioApi.closeProject(project.session_id);
      } catch {
        /* cleanup is best effort for a local session */
      }
    }
    setProject(null);
    setDatasetState(null);
    setPendingDatasetFile(null);
    setPendingDatasetProfile(null);
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
    try {
      const inspected = (await studioApi.inspectCsv(project.session_id, csvText)).profile;
      setProfile(inspected);
      setIdColumns((current) => current || inspected.id_candidates.join(", "));
      setStatus("Dataset schema inspected");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Dataset inspection failed",
      );
    }
  }
  function updateCsvText(value: string) {
    setCsvText(value);
    if (profile) {
      setProfile(null);
      setError(null);
      setStatus("CSV changed; inspect again before confirming");
    }
  }
  async function confirmCsv() {
    if (!project || confirmingCsvDataset || importingDatasetFile || (datasetStateStatus !== "none" && datasetStateStatus !== "available")) return;
    setConfirmingCsvDataset(true);
    setDatasetStateStatus("loading");
    setError(null);
    setStatus("Saving dataset contract");
    try {
      const confirmed = await studioApi.confirmCsv(
        project.session_id,
        csvText,
        target,
        task,
        idColumns.split(",").map((column) => column.trim()).filter(Boolean),
      );
      setDataset(confirmed);
      const persisted = await studioApi.getDatasetState(project.session_id);
      setDatasetState(persisted);
      setProfile(persisted.profile);
      setDatasetStateStatus("available");
      setArtifacts(await studioApi.listArtifacts(project.session_id));
      setStatus("Dataset bytes, profile, contract and audit saved");
    } catch (reason) {
      setDatasetStateStatus("error");
      setDatasetStateError(reason instanceof Error ? reason.message : "Dataset state could not be confirmed.");
      setError(
        reason instanceof Error
          ? reason.message
          : "Dataset confirmation failed",
      );
    } finally {
      setConfirmingCsvDataset(false);
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
    setTarget("");
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
    if (importingDatasetFile || confirmingCsvDataset || inspectingDatasetFile || !project || !pendingDatasetFile || !pendingDatasetProfile || !target.trim() || (datasetStateStatus !== "none" && datasetStateStatus !== "available")) return;
    setImportingDatasetFile(true);
    setDatasetStateStatus("loading");
    setError(null);
    setStatus(`Importing ${pendingDatasetFile.name}`);
    try {
      const bytes = new Uint8Array(await pendingDatasetFile.arrayBuffer());
      let binary = "";
      for (const byte of bytes) binary += String.fromCharCode(byte);
      const confirmed = await studioApi.importDataset(
        project.session_id,
        pendingDatasetFile.name,
        btoa(binary),
        target,
        task,
        idColumns.split(",").map((column) => column.trim()).filter(Boolean),
      );
      setDataset(confirmed);
      const persisted = await studioApi.getDatasetState(project.session_id);
      setDatasetState(persisted);
      setDatasetStateStatus("available");
      setProfile(persisted.profile);
      setArtifacts(await studioApi.listArtifacts(project.session_id));
      setStatus(`${pendingDatasetFile.name} saved as a verified dataset artifact`);
      setPendingDatasetFile(null);
      setPendingDatasetProfile(null);
      setError(null);
    } catch (reason) {
      setDatasetStateStatus("error");
      setDatasetStateError(reason instanceof Error ? reason.message : "Imported dataset state could not be restored.");
      setError(reason instanceof Error ? reason.message : "Dataset file import failed");
    } finally {
      setImportingDatasetFile(false);
    }
  }
  async function createGeneralization() {
    if (!project) return;
    try {
      const field = scopeField || datasetState?.contract.id_columns[0] || datasetState?.contract.feature_columns[0] || "";
      const parseValues = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);
      const supported = parseValues(supportedScopeValues);
      const forbidden = parseValues(forbiddenScopeValues);
      const created = await studioApi.createGeneralization(
        project.session_id,
        intendedUse,
        noveltyAxis,
        {
          supportedScope: field && supported.length ? [{ field, operator: "in", value: supported, rationale: "Declared supported deployment scope" }] : [],
          forbiddenScope: field && forbidden.length ? [{ field, operator: "in", value: forbidden, rationale: "Declared forbidden deployment scope" }] : [],
          unsupportedAction,
        },
      );
      setGeneralization(created);
      setScopeClassification(null);
      setStatus("Generalization contract declared");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Generalization declaration failed",
      );
    }
  }
  async function freezeGeneralization() {
    if (!project || !generalization) return;
    try {
      setGeneralization(
        await studioApi.freezeGeneralization(
          project.session_id,
          generalization.contract.contract_id,
        ),
      );
      setStatus("Generalization contract frozen");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Generalization freeze failed",
      );
    }
  }
  async function checkScope(candidateMode: "preview" | "candidate") {
    if (!project || !generalization || !datasetState?.preview.length) return;
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
      setScopeClassification(
        await studioApi.classifyGeneralizationScope(
          project.session_id,
          generalization.contract.contract_id,
          metadata,
        ),
      );
      setStatus(candidateMode === "candidate" ? "Candidate classified against declared generalization scope" : "Preview row classified against declared generalization scope");
    } catch (reason) {
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
          disabled={project.read_only}
          onUpdate={setDescription}
          placeholder="Project description"
        />
      </label>
      <Button
        view="outlined"
        size="m"
        disabled={project.read_only}
        onClick={updateDescription}
        data-ruflex-action="project.description.update"
      >
        Update description
      </Button>
      <p className="property-description">
        Description: {project.description ?? "None"}
      </p>
      <div className="artifact-details">
        <strong>Artifacts</strong>
        {artifacts.length ? (
          artifacts.map((artifact) => (
            <div key={artifact.sha256} className="mono">
              {artifact.sha256.slice(0, 12)} · {artifact.size_bytes} B ·{" "}
              {artifact.source_kind}
            </div>
          ))
        ) : (
          <span>No immutable artifacts yet.</span>
        )}
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
                onUpdate={setPath}
                placeholder="/path/to/Pump-01"
              />
            </label>
            <label className="field-label">
              Project name
              <TextInput
                aria-label="Project name"
                value={name}
                onUpdate={setName}
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
              <Button view="action" type="submit" data-ruflex-action="project.create">
                Create project
              </Button>
              <Button
                view="outlined"
                type="button"
                data-ruflex-action="project.open"
                onClick={(event) =>
                  submit(event as unknown as FormEvent, "open")
                }
              >
                Open project
              </Button>
            </div>
          </form>
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
                    <select aria-label="Target" disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} value={target} onChange={(event) => setTarget(event.target.value)}>
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
              </div>
              <div className="form-actions">
                <Button view="outlined" disabled={!datasetStateResolved || importingDatasetFile || confirmingCsvDataset} onClick={inspectCsv} data-ruflex-action="dataset.inspect">
                  Inspect dataset
                </Button>
                <Button
                  view="action"
                  disabled={!datasetStateResolved || !profile || project.read_only || confirmingCsvDataset || importingDatasetFile}
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
                  <div className="data-table-wrap"><table className="data-table"><thead><tr><th>column</th><th>proposed role</th><th>type</th></tr></thead><tbody>{pendingDatasetProfile.columns.map((column) => <tr key={column.name}><td>{column.name}</td><td>{column.proposed_role}</td><td>{column.semantic_type} · {column.dtype}</td></tr>)}</tbody></table></div>
                </div>
              )}
              {profile && !pendingDatasetFile && (
                <div className="data-summary">
                  Rows: {profile.row_count} · columns: {profile.columns.length}{" "}
                  · ID candidates: {profile.id_candidates.join(", ") || "none"}
                  <div className="info-message">Role proposals are advisory: choose target and ID columns before freezing the authoritative DatasetContract.</div>
                  <div className="data-table-wrap"><table className="data-table"><thead><tr><th>column</th><th>proposal</th><th>confidence</th><th>reason</th></tr></thead><tbody>{profile.columns.map((column) => <tr key={column.name}><td>{column.name}</td><td>{column.proposed_role}</td><td>{Math.round(column.role_confidence * 100)}%</td><td>{column.role_reason}</td></tr>)}</tbody></table></div>
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
              <div className="contract-grid">
                <label className="field-label">
                  Intended use
                  <TextInput
                    aria-label="Intended use"
                    value={intendedUse}
                    onUpdate={setIntendedUse}
                  />
                </label>
                <label className="field-label">
                  Novelty axis
                  <select
                    aria-label="Novelty axis"
                    value={noveltyAxis}
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
                    onUpdate={setScopeCandidateValue}
                    placeholder="north or external-lab"
                  />
                </label>
                <label className="field-label">
                  Supported values
                  <TextInput
                    aria-label="Supported scope values"
                    value={supportedScopeValues}
                    onUpdate={setSupportedScopeValues}
                    placeholder="north, south"
                  />
                </label>
                <label className="field-label">
                  Forbidden values
                  <TextInput
                    aria-label="Forbidden scope values"
                    value={forbiddenScopeValues}
                    onUpdate={setForbiddenScopeValues}
                    placeholder="external-lab"
                  />
                </label>
                <label className="field-label">
                  Outside declared supported scope
                  <select
                    aria-label="Unsupported scope action"
                    value={unsupportedAction}
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
                  disabled={project.read_only}
                  onClick={createGeneralization}
                  data-ruflex-action="generalization.declare"
                >
                  Declare generalization contract
                </Button>
                <Button
                  view="action"
                  disabled={
                    project.read_only ||
                    !generalization?.lint.can_freeze ||
                    !!generalization.contract.frozen_at
                  }
                  onClick={freezeGeneralization}
                  data-ruflex-action="generalization.freeze"
                >
                  Freeze evaluation contract
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
                    <Button view="outlined" disabled={!datasetState?.preview.length} onClick={() => checkScope("preview")}>Check first preview row</Button>
                    <Button view="outlined" disabled={!datasetState?.preview.length || !scopeCandidateValue.trim()} onClick={() => checkScope("candidate")}>Check candidate scope</Button>
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
          sourceExplanationId={explanation?.explanation_id ?? null}
          selectedExpertCorrectionId={selectedExpertCorrectionId}
          onExpertCorrection={setExpertCorrection}
          onFisChange={setFis}
          onEvaluation={(evaluation) => {
            setPreviousFisEvaluation(fisEvaluation);
            setFisEvaluation(evaluation);
            setFisEvaluationStatus("available");
            setFisEvaluationError(null);
            studioApi
              .listArtifacts(project.session_id)
              .then(setArtifacts)
              .catch(() => undefined);
          }}
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
          onRun={(run) => {
            setTrainingRun(run);
            setTrainingRunsReload((current) => current + 1);
            setStatus(`Training run ${run.run_id.slice(0, 8)} completed`);
            studioApi
              .listArtifacts(project.session_id)
              .then(setArtifacts)
              .catch(() => undefined);
          }}
          onStudy={(study) => { setTrainingStudy(study); setTrainingStudyStatus("available"); setTrainingStudyError(null); }}
        />
      ) : active === "ANALYSES" ? (
        <EvaluationWorkspace project={project} dataset={datasetState} datasetHydrationStatus={datasetStateStatus} datasetHydrationError={datasetStateError} onRetryDatasetHydration={() => setDatasetStateReload((current) => current + 1)} fis={fis} run={trainingRun} runs={trainingRuns} runListStatus={trainingRunsStatus} runListError={trainingRunsError} onRetryRunList={() => setTrainingRunsReload((current) => current + 1)} study={trainingStudy} evaluation={analysisEvaluation} evaluationStatus={analysisEvaluationStatus} evaluationError={analysisEvaluationError} onRetryEvaluation={() => setAnalysisEvaluationReload((current) => current + 1)} validationPolicyEvidenceStatus={validationPolicyEvidenceStatus} validationPolicyEvidenceError={validationPolicyEvidenceError} onRetryValidationPolicyEvidence={() => setValidationPolicyEvidenceReload((current) => current + 1)} calibrationTransform={calibrationTransform} decisionThreshold={decisionThreshold} finalTestEvaluation={finalTestEvaluation} finalTestEvidenceStatus={finalTestEvidenceStatus} finalTestEvidenceError={finalTestEvidenceError} onRetryFinalTestEvidence={() => setFinalTestEvidenceReload((current) => current + 1)} comparison={analysisComparison} sliceAnalysis={sliceAnalysis} selectivePolicy={selectivePolicy} stabilityGatePolicy={stabilityGatePolicy} theme={theme} onEvaluation={(evaluation) => { setAnalysisEvaluation(evaluation); setAnalysisEvaluationStatus("available"); }} onCalibration={setCalibrationTransform} onThreshold={setDecisionThreshold} onSelectivePolicy={setSelectivePolicy} onFinalTest={(evaluation) => { setFinalTestEvaluation(evaluation); if (evaluation) setFinalTestEvidenceStatus("available"); }} onComparison={setAnalysisComparison} onSliceAnalysis={setSliceAnalysis} />
      ) : active === "EVIDENCE" ? (
        <EvidenceWorkspace
          project={project}
          dataset={datasetState}
          run={trainingRun}
          evaluation={fisEvaluation}
          previousEvaluation={previousFisEvaluation}
          treeEvidence={treeEvidence}
          explanation={explanation}
          explanationCheck={explanationCheck}
          behaviorResult={behaviorResult}
          behaviorSpec={behaviorSpec}
          behaviorSpecResultStatus={behaviorSpecResultStatus}
          behaviorSpecResultError={behaviorSpecResultError}
          onRetryBehaviorSpecResult={() => setBehaviorSpecResultReload((current) => current + 1)}
          lineageBehaviorComparison={lineageBehaviorComparison}
          reproducibility={reproducibility}
          exhaustive={exhaustive}
          assurance={assurance}
          verificationBundleRecord={verificationBundleRecord}
          assuranceHydrationStatus={assuranceHydrationStatus}
          assuranceHydrationError={assuranceHydrationError}
          onRetryAssurance={() => setAssuranceHydrationReload((current) => current + 1)}
          selectivePolicy={selectivePolicy}
          generalization={generalization}
          theme={theme}
          onExplanation={setExplanation}
          onExplanationCheck={setExplanationCheck}
          onBehaviorResult={(result) => {
            setBehaviorResult(result);
            setBehaviorSpecResultStatus(result ? "available" : "none");
            setBehaviorSpecResultError(null);
          }}
          onReproducibility={setReproducibility}
          onExhaustive={setExhaustive}
          onAssurance={(value) => {
            setAssurance(value);
            setAssuranceHydrationStatus(value ? "available" : "none");
            setAssuranceHydrationError(null);
          }}
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
              <div>
                <span className="eyebrow">OPTIONAL NEXT STEP</span>
                <h2>Your dataset is ready for a model fit</h2>
                <p>Open Training to review the model and split settings. Nothing runs until you choose “Run real training”; the held-out test split stays locked.</p>
              </div>
              <Button view="action" onClick={() => setActive("STUDIES")} data-ruflex-action="project.quickstart.training">Open Training</Button>
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
              <small>{fis ? fis.name : "No model"}</small>
            </button>
            <button onClick={() => setActive("STUDIES")}>
              Studies
              <br />
              <small>
                {trainingRun ? "Training run available" : "No studies"}
              </small>
            </button>
            <button onClick={() => setActive("ANALYSES")}>
              Analyses
              <br />
              <small>
                {analysisEvaluation ? "Saved validation evaluation" : trainingRun ? "Validation analysis ready" : "No analyses"}
              </small>
            </button>
            <button onClick={() => setActive("EVIDENCE")}>
              Evidence
              <br />
              <small>
                {fisEvaluation ? "Exact trace available" : "No evidence"}
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
