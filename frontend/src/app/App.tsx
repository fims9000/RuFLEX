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
  const [overviewContextReady, setOverviewContextReady] = useState(false);
  const [pendingDatasetFile, setPendingDatasetFile] = useState<File | null>(null);
  const [pendingDatasetProfile, setPendingDatasetProfile] = useState<DatasetProfile | null>(null);
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
  const [previousFisEvaluation, setPreviousFisEvaluation] =
    useState<FISEvaluation | null>(null);
  const [trainingRun, setTrainingRun] = useState<TrainingRun | null>(null);
  const [trainingRuns, setTrainingRuns] = useState<TrainingRun[]>([]);
  const [trainingStudy, setTrainingStudy] = useState<TrainingStudy | null>(null);
  const [stabilityAnalysis, setStabilityAnalysis] = useState<StudyStabilityAnalysis | null>(null);
  const [stabilityGatePolicy, setStabilityGatePolicy] = useState<StabilityGatePolicy | null>(null);
  const [analysisEvaluation, setAnalysisEvaluation] = useState<AnalysisEvaluation | null>(null);
  const [analysisComparison, setAnalysisComparison] = useState<AnalysisComparison | null>(null);
  const [calibrationTransform, setCalibrationTransform] = useState<CalibrationTransform | null>(null);
  const [decisionThreshold, setDecisionThreshold] = useState<DecisionThresholdPolicy | null>(null);
  const [finalTestEvaluation, setFinalTestEvaluation] = useState<FinalTestEvaluation | null>(null);
  const [sliceAnalysis, setSliceAnalysis] = useState<SliceAnalysis | null>(null);
  const [treeEvidence, setTreeEvidence] = useState<TreePathEvidence | null>(null);
  const [explanation, setExplanation] = useState<ExplanationContract | null>(null);
  const [explanationCheck, setExplanationCheck] = useState<ExplanationCheck | null>(null);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorSpecResult | null>(null);
  const [behaviorSpec, setBehaviorSpec] = useState<BehaviorSpec | null>(null);
  const [lineageBehaviorComparison, setLineageBehaviorComparison] = useState<BehaviorRevisionComparison | null>(null);
  const [selectivePolicy, setSelectivePolicy] = useState<SelectivePredictionPolicy | null>(null);
  const [reproducibility, setReproducibility] = useState<ExplanationReproducibilityAnalysis | null>(null);
  const [exhaustive, setExhaustive] = useState<ExhaustiveLabResult | null>(null);
  const [assurance, setAssurance] = useState<AssuranceCase | null>(null);
  const [verificationBundleRecord, setVerificationBundleRecord] = useState<VerificationBundle | null>(null);
  const [expertCorrection, setExpertCorrection] = useState<ExpertCorrectionRevision | null>(null);
  const [lineage, setLineage] = useState<LineageGraph | null>(null);
  const [dataGovernanceObject, setDataGovernanceObject] = useState<DataGovernanceObject | null>(null);
  const [integrity, setIntegrity] = useState<ProjectIntegrityReport | null>(null);
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
      setOverviewContextReady(false);
      setFis(null);
      setFisEvaluation(null);
      setPreviousFisEvaluation(null);
      setTrainingRun(null);
      setTrainingRuns([]);
      setTrainingStudy(null);
      setAnalysisEvaluation(null);
      setAnalysisComparison(null);
      setCalibrationTransform(null);
      setDecisionThreshold(null);
      setFinalTestEvaluation(null);
      setSliceAnalysis(null);
      setTreeEvidence(null);
      setExplanation(null);
      setExplanationCheck(null);
      setBehaviorSpec(null);
      setBehaviorResult(null);
      setLineageBehaviorComparison(null);
      setSelectivePolicy(null);
      setReproducibility(null);
      setExhaustive(null);
      setAssurance(null);
      setVerificationBundleRecord(null);
      setExpertCorrection(null);
      setGeneralization(null);
      setScopeCandidateValue("");
      setScopeClassification(null);
      setLineage(null);
      setDataGovernanceObject(null);
      setIntegrity(null);
      setSelectedExpertCorrectionId(null);
      return;
    }
    setOverviewContextReady(false);
    Promise.all([
      studioApi.getDatasetState(project.session_id).catch(() => null),
      studioApi.getActiveFis(project.session_id).catch(() => null),
      studioApi.getLatestTraining(project.session_id).catch(() => null),
    ]).then(([state, activeFis, latestTraining]) => {
      if (!active) return;
      setDatasetState(state);
      setProfile(state?.profile ?? null);
      setDataset(state ? { contract: state.contract, audit: state.audit } : null);
      if (state) {
        setTarget(state.contract.target);
        setTask(state.contract.task);
        setIdColumns(state.contract.id_columns.join(", "));
      }
      setFis(activeFis);
      setTrainingRun(latestTraining);
      setOverviewContextReady(true);
    });
    studioApi
      .getLatestFisTrace(project.session_id)
      .then(setFisEvaluation)
      .catch(() => setFisEvaluation(null));
    studioApi.getTrainingRuns(project.session_id).then(setTrainingRuns).catch(() => setTrainingRuns([]));
    studioApi.getLatestBehaviorSpecResult(project.session_id).then(async (result) => {
      setBehaviorResult(result);
      const specs = await studioApi.listBehaviorSpecs(project.session_id);
      setBehaviorSpec(specs.find((candidate) => candidate.spec_id === result.spec_id) ?? null);
    }).catch(() => { setBehaviorResult(null); setBehaviorSpec(null); });
    studioApi.listStudyStabilityAnalyses(project.session_id).then((items) => setStabilityAnalysis(items.at(-1) ?? null)).catch(() => setStabilityAnalysis(null));
    studioApi.listStabilityGatePolicies(project.session_id).then((items) => setStabilityGatePolicy(items.at(-1) ?? null)).catch(() => setStabilityGatePolicy(null));
    studioApi
      .getLatestTrainingStudy(project.session_id)
      .then(setTrainingStudy)
      .catch(() => setTrainingStudy(null));
    studioApi
      .getLatestAnalysisEvaluation(project.session_id)
      .then(setAnalysisEvaluation)
      .catch(() => setAnalysisEvaluation(null));
    studioApi
      .getLatestAnalysisComparison(project.session_id)
      .then(setAnalysisComparison)
      .catch(() => setAnalysisComparison(null));
    studioApi
      .getLatestAnalysisCalibration(project.session_id)
      .then(setCalibrationTransform)
      .catch(() => setCalibrationTransform(null));
    studioApi
      .getLatestAnalysisThreshold(project.session_id)
      .then(setDecisionThreshold)
      .catch(() => setDecisionThreshold(null));
    studioApi
      .getLatestFinalTestEvaluation(project.session_id)
      .then(setFinalTestEvaluation)
      .catch(() => setFinalTestEvaluation(null));
    studioApi.getLatestSliceAnalysis(project.session_id).then(setSliceAnalysis).catch(() => setSliceAnalysis(null));
    studioApi.getLatestTreePath(project.session_id).then(setTreeEvidence).catch(() => setTreeEvidence(null));
    studioApi.getLatestExplanation(project.session_id).then(setExplanation).catch(() => setExplanation(null));
    studioApi.getLatestExplanationCheck(project.session_id).then(setExplanationCheck).catch(() => setExplanationCheck(null));
    studioApi.getLatestBehaviorResult(project.session_id).then(setBehaviorResult).catch(() => setBehaviorResult(null));
    studioApi.getLatestSelectivePolicy(project.session_id).then(setSelectivePolicy).catch(() => setSelectivePolicy(null));
    studioApi.getLatestExplanationReproducibility(project.session_id).then(setReproducibility).catch(() => setReproducibility(null));
    studioApi.getLatestExhaustiveLab(project.session_id).then(setExhaustive).catch(() => setExhaustive(null));
    studioApi.getLatestAssuranceCase(project.session_id).then(setAssurance).catch(() => setAssurance(null));
    studioApi.getLatestExpertCorrection(project.session_id).then(setExpertCorrection).catch(() => setExpertCorrection(null));
    studioApi.getActiveGeneralization(project.session_id).then(setGeneralization).catch(() => setGeneralization(null));
    studioApi.getProjectLineage(project.session_id).then(setLineage).catch(() => setLineage(null));
    studioApi.getProjectIntegrity(project.session_id).then(setIntegrity).catch(() => setIntegrity(null));
    return () => { active = false; };
  }, [project?.session_id]);
  useEffect(() => {
    if (!project) return;
    studioApi.getProjectLineage(project.session_id).then(setLineage).catch(() => undefined);
  }, [
    project?.session_id,
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
  useEffect(() => {
    if (!project || active !== "ANALYSES") return;
    studioApi.listStabilityGatePolicies(project.session_id).then((items) => setStabilityGatePolicy(items.at(-1) ?? null)).catch(() => undefined);
  }, [active, project?.session_id]);
  async function openLineageNode(node: LineageNode) {
    if (!project) return;
    const objectId = node.object_id;
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
      } else if (node.kind === "study_stability" && objectId) {
        setStabilityAnalysis(await studioApi.getStudyStabilityAnalysis(project.session_id, objectId));
      } else if (node.kind === "evaluation" && objectId) {
        setAnalysisEvaluation(await studioApi.getAnalysisEvaluation(project.session_id, objectId));
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
    if (!project) return;
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
    if (!project) return;
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
      setArtifacts(await studioApi.listArtifacts(project.session_id));
      setStatus("Dataset bytes, profile, contract and audit saved");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Dataset confirmation failed",
      );
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
    setError(null);
    if (!project || !file) return;
    setTarget("");
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
    }
  }
  async function importDatasetFile() {
    if (!project || !pendingDatasetFile || !pendingDatasetProfile || !target.trim()) return;
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
      setProfile(persisted.profile);
      setArtifacts(await studioApi.listArtifacts(project.session_id));
      setStatus(`${pendingDatasetFile.name} saved as a verified dataset artifact`);
      setPendingDatasetFile(null);
      setPendingDatasetProfile(null);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Dataset file import failed");
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
              {!dataset && !pendingDatasetFile && <div className="info-message" role="status">This CSV is an editable draft only; inspect it and confirm the dataset contract to save it.</div>}
              <label className="field-label">
                CSV data
                <textarea
                  aria-label="CSV data"
                  value={csvText}
                  onChange={(event) => updateCsvText(event.target.value)}
                  rows={8}
                />
              </label>
              <div className="contract-grid">
                <label className="field-label">
                  Target
                  {pendingDatasetProfile ? (
                    <select aria-label="Target" value={target} onChange={(event) => setTarget(event.target.value)}>
                      <option value="">Select target column</option>
                      {pendingDatasetProfile.columns.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
                    </select>
                  ) : (
                    <TextInput aria-label="Target" value={target} onUpdate={setTarget} />
                  )}
                </label>
                <label className="field-label">
                  Task
                  <select
                    aria-label="Task"
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
                  <TextInput aria-label="ID columns" value={idColumns} onUpdate={setIdColumns} placeholder={profile?.id_candidates.join(", ") || "comma-separated, optional"} />
                </label>
              </div>
              <div className="form-actions">
                <Button view="outlined" onClick={inspectCsv} data-ruflex-action="dataset.inspect">
                  Inspect dataset
                </Button>
                <Button
                  view="action"
                  disabled={!profile || project.read_only}
                  onClick={confirmCsv}
                  data-ruflex-action="dataset.confirm"
                >
                  Confirm dataset contract
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
                  disabled={project.read_only}
                  onClick={() => datasetFileInputRef.current?.click()}
                  data-ruflex-action="dataset.import"
                >
                  Import CSV / XLSX
                </Button>
                {pendingDatasetFile && (
                  <>
                    <span className="property-description">Selected: {pendingDatasetFile.name} · target: {target || "select from inspected columns"}</span>
                    <Button view="action" disabled={!pendingDatasetProfile || !target.trim() || project.read_only} onClick={importDatasetFile} data-ruflex-action="dataset.import.confirm">
                      Confirm target and import file
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
          theme={theme}
          fis={fis}
          sourceExplanationId={explanation?.explanation_id ?? null}
          selectedExpertCorrectionId={selectedExpertCorrectionId}
          onExpertCorrection={setExpertCorrection}
          onFisChange={setFis}
          onEvaluation={(evaluation) => {
            setPreviousFisEvaluation(fisEvaluation);
            setFisEvaluation(evaluation);
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
          run={trainingRun}
          study={trainingStudy}
          theme={theme}
          onRun={(run) => {
            setTrainingRun(run);
            studioApi.getTrainingRuns(project.session_id).then(setTrainingRuns).catch(() => undefined);
            setStatus(`Training run ${run.run_id.slice(0, 8)} completed`);
            studioApi
              .listArtifacts(project.session_id)
              .then(setArtifacts)
              .catch(() => undefined);
          }}
          onStudy={setTrainingStudy}
        />
      ) : active === "ANALYSES" ? (
        <EvaluationWorkspace project={project} dataset={datasetState} fis={fis} run={trainingRun} runs={trainingRuns} study={trainingStudy} evaluation={analysisEvaluation} calibrationTransform={calibrationTransform} decisionThreshold={decisionThreshold} finalTestEvaluation={finalTestEvaluation} comparison={analysisComparison} sliceAnalysis={sliceAnalysis} selectivePolicy={selectivePolicy} stabilityGatePolicy={stabilityGatePolicy} theme={theme} onEvaluation={setAnalysisEvaluation} onCalibration={setCalibrationTransform} onThreshold={setDecisionThreshold} onSelectivePolicy={setSelectivePolicy} onFinalTest={setFinalTestEvaluation} onComparison={setAnalysisComparison} onSliceAnalysis={setSliceAnalysis} />
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
          lineageBehaviorComparison={lineageBehaviorComparison}
          reproducibility={reproducibility}
          exhaustive={exhaustive}
          assurance={assurance}
          verificationBundleRecord={verificationBundleRecord}
          selectivePolicy={selectivePolicy}
          generalization={generalization}
          theme={theme}
          onExplanation={setExplanation}
          onExplanationCheck={setExplanationCheck}
          onBehaviorResult={setBehaviorResult}
          onReproducibility={setReproducibility}
          onExhaustive={setExhaustive}
          onAssurance={setAssurance}
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
          {integrity && <div className="trace-card" data-testid="project-integrity"><div className="evidence-check-header"><strong>Reopen integrity</strong><StatusBadge tone={integrity.status === "PASS" ? "success" : integrity.status === "FAIL" ? "danger" : "warning"}>{integrity.status}</StatusBadge></div><p>{integrity.checked_objects} persisted objects checked. {integrity.scientific_note}</p>{integrity.issues.map((issue) => <p className="property-description" key={`${issue.code}-${issue.path}`}>{issue.code} · {issue.path} · {issue.detail}</p>)}</div>}
          {overviewContextReady && !datasetState && !fis && !trainingRun && (
            <section className="quick-start-card" aria-label="Optional quick start">
              <div>
                <span className="eyebrow">OPTIONAL QUICK START</span>
                <h2>Start with your data</h2>
                <p>Inspect a CSV or Excel file, choose its target and task, then confirm a DatasetContract. This shortcut only opens the Data workspace; it does not start training or access the locked test split.</p>
              </div>
              <Button view="action" onClick={() => setActive("DATA")} data-ruflex-action="project.quickstart.data">Review or import data</Button>
            </section>
          )}
          <div className="project-overview-grid">
            <button onClick={() => setActive("DATA")}>
              Data
              <br />
              <small>
                {datasetState
                  ? `${datasetState.profile.row_count} rows`
                  : "No dataset"}
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
              onOpen={openLineageNode}
            />
          </div>
        </section>
      )}
    </AppShell>
  );
}
