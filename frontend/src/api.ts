export type ProjectSummary = {
  session_id: string;
  project_id: string;
  name: string;
  description: string | null;
  root: string;
  schema_version: number;
  read_only: boolean;
  modified_at: string;
};
export type ModelCatalogEntry = { key: string; label: string; family: string; available: boolean; capabilities: Record<string, boolean>; limitation: string | null };

export type LineageNode = {
  id: string;
  kind: string;
  label: string;
  detail: string | null;
  target: "PROJECT" | "DATA" | "MODELS" | "STUDIES" | "ANALYSES" | "EVIDENCE";
  object_id: string | null;
  status: string | null;
};
export type LineageEdge = { source: string; target: string; relation: string };
export type LineageGraph = { schema_version: number; nodes: LineageNode[]; edges: LineageEdge[]; scientific_note: string };

export type ArtifactRecord = {
  sha256: string;
  size_bytes: number;
  media_type: string;
  source_kind: string;
  original_name: string | null;
  parent_artifacts: string[];
  relative_blob_path: string;
  created_at: string;
};
export type DatasetProfile = {
  row_count: number;
  id_candidates: string[];
  columns: Array<{
    name: string;
    semantic_type: string;
    dtype: string;
    nullable: boolean;
  }>;
};
export type DatasetConfirmation = {
  contract: {
    dataset_fingerprint: string;
    source_artifact_sha256: string;
    target: string;
    task: string;
    feature_columns: string[];
    id_columns: string[];
    source_format: "csv" | "xlsx";
  };
  audit: {
    findings: Array<{
      code: string;
      severity: string;
      evidence: Record<string, unknown>;
      remediation: string;
    }>;
  };
};
export type ScopeRule = {
  field: string;
  operator: "in" | "not_in" | "between" | "present" | "custom";
  value: unknown;
  rationale: string;
};

export type ScopeClassification = {
  disposition: "ALLOW" | "BLOCK" | "REVIEW";
  reasons: string[];
};

export type GeneralizationContract = {
  contract_id: string;
  intended_use: string;
  frozen_at: string | null;
  unsupported_action: "BLOCK" | "REVIEW";
  supported_scope: ScopeRule[];
  forbidden_scope: ScopeRule[];
  required_subgroups: ScopeRule[];
  novelty_axes: Array<{
    axis: string;
    expected_future_relation: string;
    evaluation_requirement: string;
  }>;
};
export type GeneralizationResponse = {
  contract: GeneralizationContract;
  lint: {
    can_freeze: boolean;
    findings: Array<{ code: string; message: string }>;
  };
  recommendations: Array<{ family: string; rationale: string }>;
};
export type BehaviorSpec = {
  spec_id: string; created_at?: string; run_id: string | null; model_artifact_sha256: string | null; fis_id: string | null; fis_semantic_hash: string | null; name: string;
  kind: "output_range" | "monotonic_pair" | "invariance_pair" | "regression_case";
  sample: Record<string, number>; comparison_sample: Record<string, number> | null;
  minimum: number | null; maximum: number | null;
  expected_direction: "nondecreasing" | "nonincreasing" | null; tolerance: number; rationale: string;
};
export type BehaviorSpecResult = {
  result_id: string; created_at?: string; spec_id: string; run_id: string | null; model_artifact_sha256: string | null; fis_id: string | null; fis_semantic_hash: string | null;
  status: "PASS" | "FAIL"; observed_output: number; comparison_output: number | null; detail: string;
};
export type SelectivePredictionPolicy = {
  policy_id: string; evaluation_id: string; run_id: string; calibration_id: string | null;
  class_threshold_id: string; class_threshold: number; fit_sample_identity: string;
  confidence_cutoff: number; probability_source: "raw" | "calibrated"; risk_coverage: Array<{ confidence_cutoff: number; coverage: number; accepted_risk: number | null; accepted_count: number }>;
  scientific_note: string;
};
export type ExplanationReproducibilityAnalysis = {
  analysis_id: string; run_ids: string[]; explanation_ids: string[]; validation_case_identities: string[];
  explanation_method: string; reference_protocol: string; prediction_agreement: Record<string, number>;
  explanation_agreement: Record<string, number>; pairwise: Array<{ left_run_id: string; right_run_id: string; prediction_mean_absolute_difference: number; prediction_class_agreement: number | null; explanation_spearman: number | null; explanation_sign_agreement: number; top_k_overlap: number; case_count: number }>;
  per_feature_variability: Array<{ feature: string; mean_attribution: number; standard_deviation: number; sign_agreement: number }>; warnings: string[]; scientific_note: string;
};
export type StudyStabilityAnalysis = {
  analysis_id: string; study_id: string; dataset_fingerprint: string | null; dataset_artifact_sha256: string | null; mode: "TRAINING_VARIABILITY" | "SPLIT_VARIABILITY" | "COMBINED_VARIABILITY" | "LEGACY_COMBINED"; split_identity: string | null; split_seeds: number[]; model_kind: string;
  task: "binary_classification"; run_ids: string[]; training_seeds: number[]; split_seed: number | null; evaluation_case_identity: string | null; evaluation_id: string | null; class_threshold_id: string | null; decision_threshold: number | null; validation_alignment_status: "EXACT_MATCH" | "MIXED_CASE_IDENTITIES" | "NOT_APPLICABLE"; applicability: "APPLICABLE" | "NOT_APPLICABLE"; applicability_reason: string | null;
  selected_run_id: string; case_count: number; case_support_requirement: number; probability_source: "raw"; metric_distributions: Record<string, { mean: number; std: number; minimum: number; maximum: number; median: number; iqr: number }>;
  cases: Array<{ case_id: string; source_row: number | null; run_support_count: number; run_support_fraction: number; target: number; selected_run_probability: number; selected_run_class: number | null; mean_probability: number; std_probability: number; min_probability: number; max_probability: number; probability_range: number; majority_class: number | null; majority_class_agreement: number | null; selected_run_agreement: number | null; positive_vote_fraction: number | null; vote_entropy: number | null; run_probabilities: Record<string, number>; run_labels: Record<string, number> }>;
  high_confidence_threshold: number; unstable_agreement_threshold: number; high_confidence_instability_rate: number | null; high_confidence_case_count: number; high_confidence_unstable_case_count: number; warnings: string[]; scientific_note: string;
};
export type StabilityGatePolicy = {
  policy_id: string; study_id: string; stability_analysis_id: string; selected_run_id: string; evaluation_id: string; class_threshold_id: string | null; decision_threshold: number | null; calibration_id: string | null; dataset_fingerprint: string | null; dataset_artifact_sha256: string | null; model_kind: string; source_split: "validation"; fit_sample_identity: string; run_ids: string[]; required_run_support: number; probability_source: "raw"; analysis_schema_version: number;
  min_confidence: number; min_class_agreement: number; max_probability_std: number; test_status: "LOCKED_NOT_EVALUATED";
  decisions: Array<{ case_id: string; disposition: "ACCEPT" | "REVIEW" | "BLOCK"; reasons: Array<"LOW_CONFIDENCE" | "RUN_DISAGREEMENT" | "HIGH_DISPERSION" | "OUT_OF_SCOPE" | "INSUFFICIENT_RUN_SUPPORT">; selected_run_probability: number; confidence: number; majority_class_agreement: number; selected_run_agreement: number; probability_std: number; run_support_count: number }>;
  risk_coverage: Array<{ policy: "NO_REVIEW" | "RANDOM_REVIEW" | "CONFIDENCE_ONLY" | "STABILITY_AWARE"; coverage: number; accepted_count: number; accepted_risk: number | null }>;
  scientific_note: string;
};
export type StabilityGateApplication = { policy_id: string; selected_run_id: string; disposition: "ACCEPT" | "REVIEW" | "BLOCK"; reasons: Array<"LOW_CONFIDENCE" | "RUN_DISAGREEMENT" | "HIGH_DISPERSION" | "OUT_OF_SCOPE" | "INSUFFICIENT_RUN_SUPPORT">; selected_run_probability: number; predicted_label: number; confidence: number; majority_class_agreement: number; selected_run_agreement: number; probability_std: number; run_support_count: number; run_probabilities: Record<string, number> };
export type ExhaustiveLabResult = { result_id: string; kind: "decision_tree_structure" | "fis_discrete_grid"; exactness_label: "EXACT_FINITE_STRUCTURE" | "EXACT_ON_DECLARED_DISCRETE_GRID"; run_id: string | null; fis_semantic_hash: string | null; declared_grid: Record<string, number[]>; state_count: number; state_estimate: number; max_states: number; paths: Array<Record<string, unknown>>; uncovered_states: Array<Record<string, unknown>>; dead_rules: string[]; conflict_states: Array<Record<string, unknown>>; scientific_note: string };
export type AssuranceCase = { assurance_id: string; gates: Array<{ key: string; status: "PASS" | "WARN" | "FAIL" | "NOT_AVAILABLE"; evidence: string[]; risk: string | null }>; unresolved_risks: string[]; scientific_note: string };
export type ConditionMonitoringDemo = { demo_id: string; policy_id: string; telemetry: Record<string, number>; predicted_class: number; probability: number; confidence: number; decision: "ACCEPT" | "REVIEW" | "OUT_OF_SCOPE"; scope_disposition: string; explanation_id: string | null; explanation_check_id: string | null; assurance_id: string | null; verification_bundle_sha256: string | null; explanation_note: string; safety_note: string };

const apiBase = import.meta.env.VITE_RUFLEX_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function requestText(path: string): Promise<string> {
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `Request failed (${response.status})`);
  }
  return response.text();
}

export const studioApi = {
  health: () => request<{ status: string }>("/api/health"),
  getModelCatalog: () => request<ModelCatalogEntry[]>("/api/model-catalog"),
  createProject: (path: string, name: string) =>
    request<ProjectSummary>("/api/projects", { path, name }),
  openProject: (path: string, readOnly = false) =>
    request<ProjectSummary>("/api/projects/open", {
      path,
      read_only: readOnly,
    }),
  saveProject: (sessionId: string) =>
    request<ProjectSummary>("/api/projects/save", { session_id: sessionId }),
  updateProjectMetadata: (sessionId: string, description: string) =>
    request<ProjectSummary>("/api/projects/metadata", {
      session_id: sessionId,
      description: description || null,
    }),
  closeProject: (sessionId: string) =>
    request<void>("/api/projects/close", { session_id: sessionId }),
  getProjectLineage: (sessionId: string) =>
    request<LineageGraph>(`/api/projects/${sessionId}/lineage`),
  listArtifacts: (sessionId: string) =>
    request<ArtifactRecord[]>(`/api/projects/${sessionId}/artifacts`),
  ingestTextArtifact: (sessionId: string, text: string) =>
    request<{ sha256: string }>("/api/projects/artifacts/text", {
      session_id: sessionId,
      text,
      original_name: "studio-note.txt",
    }),
  inspectCsv: (sessionId: string, csvText: string) =>
    request<{ profile: DatasetProfile }>("/api/projects/dataset/inspect", {
      session_id: sessionId,
      csv_text: csvText,
    }),
  confirmCsv: (
    sessionId: string,
    csvText: string,
    target: string,
    task: string,
    idColumns: string[],
  ) =>
    request<DatasetConfirmation>("/api/projects/dataset/confirm", {
      session_id: sessionId,
      csv_text: csvText,
      target,
      task,
      id_columns: idColumns,
    }),
  importDataset: (
    sessionId: string,
    filename: string,
    contentBase64: string,
    target: string,
    task: string,
    idColumns: string[],
  ) =>
    request<DatasetConfirmation>("/api/projects/dataset/import", {
      session_id: sessionId,
      filename,
      content_base64: contentBase64,
      target,
      task,
      id_columns: idColumns,
    }),
  createGeneralization: (
    sessionId: string,
    intendedUse: string,
    axis: string,
    options?: {
      supportedScope?: ScopeRule[];
      forbiddenScope?: ScopeRule[];
      requiredSubgroups?: ScopeRule[];
      unsupportedAction?: "BLOCK" | "REVIEW";
    },
  ) =>
    request<GeneralizationResponse>("/api/projects/generalization/contracts", {
      session_id: sessionId,
      intended_use: intendedUse,
      novelty_axes: [
        {
          axis,
          expected_future_relation: "unseen future data",
          evaluation_requirement: "hold out by declared axis",
        },
      ],
      supported_scope: options?.supportedScope ?? [],
      forbidden_scope: options?.forbiddenScope ?? [],
      required_subgroups: options?.requiredSubgroups ?? [],
      unsupported_action: options?.unsupportedAction ?? "BLOCK",
    }),
  getActiveGeneralization: (sessionId: string) =>
    request<GeneralizationResponse>(
      `/api/projects/${sessionId}/generalization/contracts/active`,
    ),
  getGeneralization: (sessionId: string, contractId: string) =>
    request<GeneralizationResponse>(
      `/api/projects/${sessionId}/generalization/contracts/${contractId}`,
    ),
  freezeGeneralization: (sessionId: string, contractId: string) =>
    request<GeneralizationResponse>(
      `/api/projects/generalization/contracts/${contractId}/freeze`,
      { session_id: sessionId },
    ),
  classifyGeneralizationScope: (
    sessionId: string,
    contractId: string,
    sampleMetadata: Record<string, unknown>,
  ) =>
    request<ScopeClassification>(
      `/api/projects/generalization/contracts/${contractId}/classify`,
      { session_id: sessionId, sample_metadata: sampleMetadata },
    ),
  getDatasetState: (sessionId: string) =>
    request<DatasetState>(`/api/projects/${sessionId}/dataset`),
  getDatasetFeatureRange: (sessionId: string, featureName: string) =>
    request<{ minimum: number; maximum: number }>(
      `/api/projects/${sessionId}/dataset/features/${encodeURIComponent(featureName)}/range`,
    ),
  createDefaultFis: (
    sessionId: string,
    name = "Risk FIS",
    inputColumns?: string[],
  ) =>
    request<FISSpec>("/api/projects/fis/default", {
      session_id: sessionId,
      name,
      input_columns: inputColumns ?? null,
    }),
  importMatlabFis: (sessionId: string, source: string) =>
    request<{ spec: FISSpec | null; issues: FISCompatibilityIssue[] }>(
      "/api/projects/fis/import/matlab",
      { session_id: sessionId, source },
    ),
  exportMatlabFis: (sessionId: string) =>
    requestText(`/api/projects/${sessionId}/fis/export/matlab`),
  getActiveFis: (sessionId: string) =>
    request<FISSpec>(`/api/projects/${sessionId}/fis/active`),
  getFisRevisions: (sessionId: string) =>
    request<FISSpec[]>(`/api/projects/${sessionId}/fis/revisions`),
  getCanonicalFisJson: (sessionId: string) =>
    requestText(`/api/projects/${sessionId}/fis/canonical.json`),
  getCanonicalFisYaml: (sessionId: string) =>
    requestText(`/api/projects/${sessionId}/fis/canonical.yaml`),
  saveFis: (sessionId: string, spec: FISSpec) =>
    request<FISSpec>("/api/projects/fis/save", { session_id: sessionId, spec }),
  refitSugenoConsequents: (sessionId: string, lockedRuleIds: string[], sourceExplanationId: string | null = null) =>
    request<ExpertCorrectionResult>("/api/projects/fis/expert-correction", {
      session_id: sessionId,
      locked_rule_ids: lockedRuleIds,
      source_explanation_id: sourceExplanationId,
    }),
  getLatestExpertCorrection: (sessionId: string) =>
    request<ExpertCorrectionRevision>(`/api/projects/${sessionId}/fis/expert-correction/latest`),
  getExpertCorrection: (sessionId: string, correctionId: string) =>
    request<ExpertCorrectionRevision>(`/api/projects/${sessionId}/fis/expert-correction/${correctionId}`),
  diagnoseFis: (sessionId: string, spec: FISSpec) =>
    request<Array<{ code: string; severity: string; message: string }>>(
      "/api/projects/fis/diagnostics",
      { session_id: sessionId, spec },
    ),
  evaluateFis: (
    sessionId: string,
    inputs: Record<string, number>,
    persistTrace = true,
  ) =>
    request<FISEvaluation>("/api/projects/fis/evaluate", {
      session_id: sessionId,
      inputs,
      persist_trace: persistTrace,
    }),
  getLatestFisTrace: async (sessionId: string): Promise<FISEvaluation> => ({
    evaluation: await request<FISEvaluation["evaluation"]>(
      `/api/projects/${sessionId}/fis/trace/latest`,
    ),
    trace_artifact_sha256: null,
  }),
  previewResponseSurface: (
    sessionId: string,
    spec: FISSpec,
    xVariable: string,
    yVariable: string,
    fixedInputs: Record<string, number>,
  ) =>
    request<ResponseSurface>("/api/projects/fis/response-surface", {
      session_id: sessionId,
      spec,
      x_variable: xVariable,
      y_variable: yVariable,
      fixed_inputs: fixedInputs,
    }),
  runTraining: (
    sessionId: string,
    config: {
      model_kind?: "flat_neuro_fuzzy" | "logistic_regression" | "linear_regression" | "decision_tree" | "random_forest" | "gradient_boosting";
      seed: number;
      split_seed?: number | null;
      training_seed?: number | null;
      max_epochs: number;
      learning_rate: number;
      batch_size: number;
      patience: number | null;
      validation_fraction: number;
      test_fraction: number;
      max_rules: number;
    },
  ) =>
    request<TrainingRun>("/api/projects/training/run", {
      session_id: sessionId,
      ...config,
    }),
  getLatestTraining: (sessionId: string) =>
    request<TrainingRun>(`/api/projects/${sessionId}/training/latest`),
  getTrainingRuns: (sessionId: string) =>
    request<TrainingRun[]>(`/api/projects/${sessionId}/training/runs`),
  getTrainingRun: (sessionId: string, runId: string) =>
    request<TrainingRun>(`/api/projects/${sessionId}/training/runs/${runId}`),
  createTreePath: (sessionId: string, runId: string, sample: Record<string, number>) =>
    request<TreePathEvidence>("/api/projects/training/tree-path", { session_id: sessionId, run_id: runId, sample }),
  getLatestTreePath: (sessionId: string) =>
    request<TreePathEvidence>(`/api/projects/${sessionId}/evidence/tree-path/latest`),
  getTreePath: (sessionId: string, evidenceId: string) =>
    request<TreePathEvidence>(`/api/projects/${sessionId}/evidence/tree-path/${evidenceId}`),
  createOcclusionExplanation: (sessionId: string, runId: string, sample: Record<string, number>) =>
    request<ExplanationContract>("/api/projects/evidence/explanations/occlusion", { session_id: sessionId, run_id: runId, sample }),
  createPosthocExplanation: (sessionId: string, runId: string, sample: Record<string, number>, method: "occlusion" | "integrated_gradients" | "gradient_shap" | "shap" | "tree_shap") =>
    request<ExplanationContract>("/api/projects/evidence/explanations", { session_id: sessionId, run_id: runId, sample, method }),
  getLatestExplanation: (sessionId: string) =>
    request<ExplanationContract>(`/api/projects/${sessionId}/evidence/explanations/latest`),
  getExplanation: (sessionId: string, explanationId: string) =>
    request<ExplanationContract>(`/api/projects/${sessionId}/evidence/explanations/${explanationId}`),
  checkExplanation: (sessionId: string, explanationId: string) =>
    request<ExplanationCheck>("/api/projects/evidence/explanation-checks", { session_id: sessionId, explanation_id: explanationId }),
  getLatestExplanationCheck: (sessionId: string) =>
    request<ExplanationCheck>(`/api/projects/${sessionId}/evidence/explanation-checks/latest`),
  getExplanationCheck: (sessionId: string, checkId: string) =>
    request<ExplanationCheck>(`/api/projects/${sessionId}/evidence/explanation-checks/${checkId}`),
  createBehaviorSpec: (sessionId: string, payload: Omit<BehaviorSpec, "spec_id" | "model_artifact_sha256" | "fis_id" | "fis_semantic_hash" | "created_at">) =>
    request<BehaviorSpec>("/api/projects/evidence/behavior-specs", { session_id: sessionId, ...payload }),
  runBehaviorSpec: (sessionId: string, specId: string) =>
    request<BehaviorSpecResult>("/api/projects/evidence/behavior-specs/run", { session_id: sessionId, spec_id: specId }),
  getLatestBehaviorResult: (sessionId: string) =>
    request<BehaviorSpecResult>(`/api/projects/${sessionId}/evidence/behavior-specs/latest`),
  listBehaviorSpecs: (sessionId: string) =>
    request<BehaviorSpec[]>(`/api/projects/${sessionId}/evidence/behavior-specs`),
  listBehaviorResults: (sessionId: string) =>
    request<BehaviorSpecResult[]>(`/api/projects/${sessionId}/evidence/behavior-specs/results`),
  createSelectivePolicy: (sessionId: string, evaluationId: string, confidenceCutoff: number, calibrationId: string | null, thresholdId: string | null) =>
    request<SelectivePredictionPolicy>("/api/projects/analyses/selective-policies", { session_id: sessionId, evaluation_id: evaluationId, confidence_cutoff: confidenceCutoff, calibration_id: calibrationId, threshold_id: thresholdId }),
  createStudyStabilityAnalysis: (sessionId: string, studyId: string, evaluationId: string | null, thresholdId: string | null, highConfidenceThreshold = .9, unstableAgreementThreshold = .8) =>
    request<StudyStabilityAnalysis>("/api/projects/analyses/stability", { session_id: sessionId, study_id: studyId, evaluation_id: evaluationId, threshold_id: thresholdId, high_confidence_threshold: highConfidenceThreshold, unstable_agreement_threshold: unstableAgreementThreshold }),
  listStudyStabilityAnalyses: (sessionId: string) => request<StudyStabilityAnalysis[]>(`/api/projects/${sessionId}/analyses/stability`),
  createStabilityGatePolicy: (sessionId: string, analysisId: string, evaluationId: string, minConfidence: number, minAgreement: number, maxProbabilityStd: number, calibrationId: string | null = null) =>
    request<StabilityGatePolicy>("/api/projects/analyses/stability-policies", { session_id: sessionId, analysis_id: analysisId, evaluation_id: evaluationId, min_confidence: minConfidence, min_class_agreement: minAgreement, max_probability_std: maxProbabilityStd, calibration_id: calibrationId }),
  listStabilityGatePolicies: (sessionId: string) => request<StabilityGatePolicy[]>(`/api/projects/${sessionId}/analyses/stability-policies`),
  applyStabilityGatePolicy: (sessionId: string, policyId: string, sample: Record<string, number>, metadata: Record<string, unknown> = {}, generalizationContractId: string | null = null) => request<StabilityGateApplication>("/api/projects/analyses/stability-policies/apply", { session_id: sessionId, policy_id: policyId, sample, metadata, generalization_contract_id: generalizationContractId }),
  getLatestSelectivePolicy: (sessionId: string) =>
    request<SelectivePredictionPolicy>(`/api/projects/${sessionId}/analyses/selective-policies/latest`),
  applySelectivePolicy: (sessionId: string, policyId: string, sample: Record<string, number>, metadata: Record<string, unknown> = {}, generalizationContractId: string | null = null) =>
    request<{ policy_id: string; probability: number; predicted_label: number; confidence: number; disposition: "ACCEPT" | "REVIEW" | "OUT_OF_SCOPE"; scope_disposition: string; reasons: string[] }>("/api/projects/analyses/selective-policies/apply", { session_id: sessionId, policy_id: policyId, sample, metadata, generalization_contract_id: generalizationContractId }),
  runConditionMonitoringDemo: (sessionId: string, telemetry: Record<string, number>, policyId: string | null, generalizationContractId: string | null) => request<ConditionMonitoringDemo>("/api/projects/evidence/condition-monitoring-demo", { session_id: sessionId, telemetry, policy_id: policyId, generalization_contract_id: generalizationContractId }),
  getLatestConditionMonitoringDemo: (sessionId: string) => request<ConditionMonitoringDemo>(`/api/projects/${sessionId}/evidence/condition-monitoring-demo/latest`),
  listExplanations: (sessionId: string) => request<ExplanationContract[]>(`/api/projects/${sessionId}/evidence/explanations`),
  createExplanationReproducibility: (sessionId: string, explanationIds: string[]) =>
    request<ExplanationReproducibilityAnalysis>("/api/projects/evidence/explanation-reproducibility", { session_id: sessionId, explanation_ids: explanationIds }),
  getLatestExplanationReproducibility: (sessionId: string) => request<ExplanationReproducibilityAnalysis>(`/api/projects/${sessionId}/evidence/explanation-reproducibility/latest`),
  runExhaustiveLab: (sessionId: string, kind: ExhaustiveLabResult["kind"], runId: string | null, gridPoints = 3, maxStates = 10000) => request<ExhaustiveLabResult>("/api/projects/evidence/exhaustive-lab", { session_id: sessionId, kind, run_id: runId, grid_points: gridPoints, max_states: maxStates }),
  getLatestExhaustiveLab: (sessionId: string) => request<ExhaustiveLabResult>(`/api/projects/${sessionId}/evidence/exhaustive-lab/latest`),
  createAssuranceCase: (sessionId: string) => request<AssuranceCase>("/api/projects/evidence/assurance-cases", { session_id: sessionId }),
  getLatestAssuranceCase: (sessionId: string) => request<AssuranceCase>(`/api/projects/${sessionId}/evidence/assurance-cases/latest`),
  exportVerificationBundle: (sessionId: string) => request<{ path: string; sha256: string; entry_count: number }>("/api/projects/evidence/verification-bundles", { session_id: sessionId }),
  runMultiSeedStudy: (
    sessionId: string,
    config: {
      name: string;
      model_kind: "flat_neuro_fuzzy" | "logistic_regression" | "linear_regression" | "decision_tree" | "random_forest" | "gradient_boosting";
      seeds: number[];
      randomness_protocol?: "LEGACY_COMBINED" | "TRAINING_VARIABILITY" | "SPLIT_VARIABILITY" | "COMBINED_VARIABILITY";
      split_seed?: number | null;
      training_seed?: number | null;
      selection_metric: string;
      max_epochs: number;
      learning_rate: number;
      batch_size: number;
      patience: number | null;
      validation_fraction: number;
      test_fraction: number;
      max_rules: number;
    },
  ) =>
    request<TrainingStudy>("/api/projects/training/studies", {
      session_id: sessionId,
      ...config,
    }),
  getLatestTrainingStudy: (sessionId: string) =>
    request<TrainingStudy>(`/api/projects/${sessionId}/training/studies/latest`),
  getTrainingStudy: (sessionId: string, studyId: string) =>
    request<TrainingStudy>(`/api/projects/${sessionId}/training/studies/${studyId}`),
  startStudyJob: (sessionId: string, config: { name: string; model_kind: "flat_neuro_fuzzy" | "logistic_regression" | "linear_regression" | "decision_tree" | "random_forest" | "gradient_boosting"; seeds: number[]; randomness_protocol?: "LEGACY_COMBINED" | "TRAINING_VARIABILITY" | "SPLIT_VARIABILITY" | "COMBINED_VARIABILITY"; split_seed?: number | null; training_seed?: number | null; selection_metric: string; max_epochs: number; learning_rate: number; batch_size: number; patience: number | null; validation_fraction: number; test_fraction: number; max_rules: number }) =>
    request<StudyJob>("/api/projects/training/study-jobs", { session_id: sessionId, ...config }),
  getStudyJob: (sessionId: string, jobId: string) =>
    request<StudyJob>(`/api/projects/${sessionId}/training/study-jobs/${jobId}`),
  cancelStudyJob: (sessionId: string, jobId: string) =>
    request<StudyJob>(`/api/projects/${sessionId}/training/study-jobs/${jobId}/cancel`, {}),
  createAnalysisEvaluation: (sessionId: string, runId: string) =>
    request<AnalysisEvaluation>("/api/projects/analyses/evaluations", {
      session_id: sessionId,
      run_id: runId,
    }),
  getLatestAnalysisEvaluation: (sessionId: string) =>
    request<AnalysisEvaluation>(`/api/projects/${sessionId}/analyses/evaluations/latest`),
  getAnalysisEvaluation: (sessionId: string, evaluationId: string) =>
    request<AnalysisEvaluation>(`/api/projects/${sessionId}/analyses/evaluations/${evaluationId}`),
  fitAnalysisCalibration: (sessionId: string, evaluationId: string) =>
    request<CalibrationTransform>("/api/projects/analyses/calibrations", {
      session_id: sessionId,
      evaluation_id: evaluationId,
    }),
  getLatestAnalysisCalibration: (sessionId: string) =>
    request<CalibrationTransform>(`/api/projects/${sessionId}/analyses/calibrations/latest`),
  getAnalysisCalibration: (sessionId: string, calibrationId: string) =>
    request<CalibrationTransform>(`/api/projects/${sessionId}/analyses/calibrations/${calibrationId}`),
  selectAnalysisThreshold: (sessionId: string, evaluationId: string, calibrationId?: string | null) =>
    request<DecisionThresholdPolicy>("/api/projects/analyses/thresholds", {
      session_id: sessionId,
      evaluation_id: evaluationId,
      calibration_id: calibrationId ?? null,
      objective: "f1",
    }),
  getLatestAnalysisThreshold: (sessionId: string) =>
    request<DecisionThresholdPolicy>(`/api/projects/${sessionId}/analyses/thresholds/latest`),
  getAnalysisThreshold: (sessionId: string, thresholdId: string) =>
    request<DecisionThresholdPolicy>(`/api/projects/${sessionId}/analyses/thresholds/${thresholdId}`),
  evaluateFinalTest: (sessionId: string, evaluationId: string, calibrationId?: string | null, thresholdId?: string | null, selectivePolicyId?: string | null, stabilityGatePolicyId?: string | null) =>
    request<FinalTestEvaluation>("/api/projects/analyses/final-test", {
      session_id: sessionId,
      evaluation_id: evaluationId,
      calibration_id: calibrationId ?? null,
      threshold_id: thresholdId ?? null,
      selective_policy_id: selectivePolicyId ?? null,
      stability_gate_policy_id: stabilityGatePolicyId ?? null,
    }),
  getLatestFinalTestEvaluation: (sessionId: string) =>
    request<FinalTestEvaluation>(`/api/projects/${sessionId}/analyses/final-test/latest`),
  getFinalTestEvaluation: (sessionId: string, finalTestId: string) =>
    request<FinalTestEvaluation>(`/api/projects/${sessionId}/analyses/final-test/${finalTestId}`),
  createAnalysisComparison: (sessionId: string, runIds: string[], includeActiveFis = false) =>
    request<AnalysisComparison>("/api/projects/analyses/comparisons", {
      session_id: sessionId,
      run_ids: runIds,
      include_active_fis: includeActiveFis,
    }),
  getLatestAnalysisComparison: (sessionId: string) =>
    request<AnalysisComparison>(`/api/projects/${sessionId}/analyses/comparisons/latest`),
  getAnalysisComparison: (sessionId: string, comparisonId: string) =>
    request<AnalysisComparison>(`/api/projects/${sessionId}/analyses/comparisons/${comparisonId}`),
  createSliceAnalysis: (sessionId: string, evaluationId: string, metric: string | null, definitions: SliceDefinition[]) =>
    request<SliceAnalysis>("/api/projects/analyses/slices", { session_id: sessionId, evaluation_id: evaluationId, metric, definitions }),
  getLatestSliceAnalysis: (sessionId: string) =>
    request<SliceAnalysis>(`/api/projects/${sessionId}/analyses/slices/latest`),
  getSliceAnalysis: (sessionId: string, analysisId: string) =>
    request<SliceAnalysis>(`/api/projects/${sessionId}/analyses/slices/${analysisId}`),
};

export type DatasetState = {
  profile: DatasetProfile;
  contract: DatasetConfirmation["contract"];
  audit: DatasetConfirmation["audit"];
  preview: Array<Record<string, unknown>>;
};

export type TrainingStudy = {
  study_id: string;
  name: string;
  model_kind: TrainingRun["model_kind"];
  task: "regression" | "binary_classification";
  selection_metric: string;
  selection_split: "validation";
  selection_rule: "min" | "max";
  seed_runs: TrainingRun[];
  selected_run_id: string;
  selection_reason: string;
  randomness_protocol: "LEGACY_COMBINED" | "TRAINING_VARIABILITY" | "SPLIT_VARIABILITY" | "COMBINED_VARIABILITY";
  split_seed: number | null;
  training_seeds: number[];
};

export type StudyJob = {
  job_id: string;
  name: string;
  model_kind: TrainingRun["model_kind"];
  selection_metric: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  cancel_requested: boolean;
  seed_states: Array<{ seed: number; status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED"; run_id: string | null; runtime_seconds: number | null; error: string | null }>;
  study_id: string | null;
  error: string | null;
};

export type AnalysisEvaluation = {
  schema_version: number;
  evaluation_id: string;
  created_at: string;
  run_id: string;
  task: "regression" | "binary_classification";
  target: string;
  model_kind: string | null;
  model_artifact_sha256: string | null;
  dataset_fingerprint: string | null;
  dataset_artifact_sha256: string | null;
  preprocessing_identity: string | null;
  split: "validation";
  test_status: "LOCKED_NOT_EVALUATED";
  metrics: Record<string, number>;
  prediction_preview: TrainingRun["prediction_preview"];
  validation_row_count: number;
  confusion_matrix: TrainingRun["confusion_matrix"];
  calibration: {
    method: "validation_reliability_bins" | "platt_scaling";
    fit_scope: "not_fitted" | "validation_only";
    status: "DESCRIPTIVE_NOT_CALIBRATED" | "FITTED_VALIDATION_ONLY";
    bin_count: number;
    parameters: Record<string, number>;
    fit_sample_identity: string | null;
  };
  calibration_bins: TrainingRun["calibration"];
  threshold: { selected_threshold: number } | null;
  scientific_note: string;
};

export type CalibrationTransform = {
  schema_version: number;
  calibration_id: string;
  created_at: string;
  evaluation_id: string;
  run_id: string;
  method: "platt_scaling";
  source_split: "validation";
  test_status: "LOCKED_NOT_EVALUATED";
  input_kind: "model_logit";
  fit_sample_count: number;
  fit_sample_identity: string;
  coefficient: number;
  intercept: number;
  brier_before: number;
  brier_after: number;
  ece_before: number;
  ece_after: number;
  calibration_bins: TrainingRun["calibration"];
  predictions: Array<{
    row: number;
    source_row?: number | null;
    target: number;
    raw_probability: number;
    calibrated_probability: number;
  }>;
  scientific_note: string;
};

export type DecisionThresholdPolicy = {
  schema_version: number;
  threshold_id: string;
  created_at: string;
  evaluation_id: string;
  run_id: string;
  calibration_id: string | null;
  source_split: "validation";
  test_status: "LOCKED_NOT_EVALUATED";
  objective: "f1";
  probability_source: "raw" | "calibrated";
  candidate_rule: string;
  selected_threshold: number;
  selection_result: number;
  fit_sample_identity: string;
  metrics: Record<string, number>;
  confusion_matrix: NonNullable<TrainingRun["confusion_matrix"]>;
  decisions: Array<{
    row: number;
    target: number;
    probability: number;
    predicted_label: number;
  }>;
  scientific_note: string;
};

export type FinalTestEvaluation = {
  schema_version: number;
  final_test_id: string;
  created_at: string;
  run_id: string;
  evaluation_id: string;
  task: "regression" | "binary_classification";
  target: string;
  model_kind: string;
  model_artifact_sha256: string;
  dataset_fingerprint: string;
  dataset_artifact_sha256: string;
  preprocessing_identity: string;
  split: "test";
  status: "FINAL_TEST_EVALUATED";
  calibration_id: string | null;
  threshold_id: string | null;
  selective_policy_id: string | null;
  stability_gate_policy_id: string | null;
  probability_source: "not_applicable" | "raw" | "calibrated";
  decision_threshold: number | null;
  metrics: Record<string, number>;
  prediction_rows: TrainingRun["prediction_preview"];
  test_row_count: number;
  confusion_matrix: TrainingRun["confusion_matrix"];
  calibration_bins: TrainingRun["calibration"];
  test_sample_identity: string;
  test_case_identity: string | null;
  policy_identity: string;
  policy_frozen_at: string | null;
  dataset_test_unlock_at: string | null;
  scientific_note: string;
};

export type AnalysisComparison = {
  schema_version: number;
  comparison_id: string;
  created_at: string;
  task: "regression" | "binary_classification";
  target: string;
  split: "validation";
  run_ids: string[];
  dataset_fingerprint: string | null;
  validation_alignment: "same_cases" | "mixed_cases" | "unknown";
  validation_sample_identities: Record<string, string>;
  fis_id: string | null;
  fis_semantic_hash: string | null;
  metric_rows: Array<Record<string, string | number>>;
  scientific_note: string;
};

export type SliceDefinition = {
  name: string;
  kind: "categorical" | "numeric_range" | "group" | "temporal" | "manual";
  field?: string | null;
  values?: Array<string | number>;
  minimum?: number | null;
  maximum?: number | null;
  start?: string | null;
  end?: string | null;
  source_rows?: number[];
};

export type SliceAnalysis = {
  schema_version: number;
  analysis_id: string;
  created_at: string;
  evaluation_id: string;
  run_id: string;
  dataset_fingerprint: string;
  generalization_contract_id: string | null;
  source_split: "validation";
  test_status: "LOCKED_NOT_EVALUATED";
  metric: string;
  definitions: SliceDefinition[];
  results: Array<{
    name: string;
    kind: string;
    n: number;
    metric: string;
    value: number | null;
    overall_value: number;
    delta_vs_overall: number | null;
    status: "OK" | "WARN" | "EMPTY";
    warning: string | null;
    scope_disposition: "ALLOW" | "REVIEW" | "BLOCK" | "UNDECLARED" | "EMPTY";
    scope_reasons: string[];
  }>;
  scientific_note: string;
};

export type TreePathEvidence = {
  evidence_id: string;
  run_id: string;
  model_artifact_sha256: string;
  preprocessing_identity: string;
  input_sample: Record<string, number>;
  steps: Array<{ node_id: number; feature_name: string; threshold: number; value: number; decision: "left" | "right" }>;
  leaf_id: number;
  prediction: number;
  class_probabilities: Record<string, number> | null;
  label: "EXACT TREE EXECUTION PATH";
};

export type ExplanationContract = {
  schema_version: number;
  explanation_id: string;
  created_at: string;
  run_id: string;
  model_kind: TrainingRun["model_kind"];
  model_artifact_sha256: string;
  preprocessing_identity: string | null;
  sample_identity: string | null;
  reference_identity: string | null;
  sample: Record<string, number>;
  target: string;
  scope: "local_sample";
  family: "occlusion" | "integrated_gradients" | "gradient_shap" | "shap" | "tree_shap";
  method: "train_reference_occlusion" | "integrated_gradients_train_reference" | "gradient_shap_train_background" | "permutation_shap_train_background" | "tree_shap_train_background";
  epistemic_category: "POST-HOC ATTRIBUTION";
  exactness: "post_hoc";
  prediction: number;
  output_space: "prediction" | "probability" | "raw_score";
  base_value: number | null;
  completeness_error: number | null;
  reference_definition: string;
  feature_representation: string;
  assumptions: string[];
  limitations: string[];
  attributions: Array<{
    feature: string;
    observed_value: number;
    reference_value: number;
    attribution: number;
    occluded_prediction: number | null;
  }>;
  scientific_note: string;
};

export type ExplanationCheck = {
  schema_version: number;
  check_id: string;
  created_at: string;
  explanation_id: string;
  run_id: string;
  status: "PASSED_AVAILABLE_CHECKS" | "WARNING" | "FAILED";
  checks: Array<{ name: string; status: "PASS" | "WARN" | "FAIL" | "N/A"; detail: string }>;
  scientific_note: string;
};

export type ExpertCorrectionRevision = {
  schema_version: number;
  correction_id: string;
  created_at: string;
  fis_id: string;
  source_semantic_hash: string;
  result_semantic_hash: string;
  dataset_fingerprint: string;
  target: string;
  split_seed: number;
  validation_fraction: number;
  test_fraction: number;
  train_row_count: number;
  skipped_row_count: number;
  locked_rule_ids: string[];
  fitted_rule_ids: string[];
  source_explanation_id: string | null;
  train_rmse_before: number;
  train_rmse_after: number;
  validation_row_count: number;
  validation_rmse_before: number | null;
  validation_rmse_after: number | null;
  fit_method: string;
  test_status: string;
  scientific_note: string;
};

export type ExpertCorrectionResult = {
  correction: ExpertCorrectionRevision;
  fis: FISSpec;
};

export type MembershipFunction = {
  name: string;
  kind:
    | "triangular"
    | "trapezoidal"
    | "gaussian"
    | "bell"
    | "sigmoid"
    | "s_shape"
    | "z_shape"
    | "pi_shape";
  parameters: number[];
  locked?: boolean;
};
export type FuzzyVariable = {
  name: string;
  minimum: number;
  maximum: number;
  terms: MembershipFunction[];
  role: "input" | "output";
  dataset_feature: string | null;
  units: string | null;
  locked: boolean;
};
export type FISCompatibilityIssue = {
  source_construct: string;
  ruflex_construct: string | null;
  semantic_consequence: string;
  severity: string;
  status: "SUPPORTED" | "CONVERTED" | "APPROXIMATED" | "UNSUPPORTED" | "DROPPED";
};
export type FuzzyRule = {
  rule_id: string;
  name: string;
  clauses: Array<{ variable: string; term: string }>;
  connector: "and" | "or";
  output_term: string;
  weight: number;
  enabled: boolean;
  sugeno_consequent: SugenoConsequent | null;
};
export type SugenoConsequent = {
  kind: "constant" | "linear";
  constant: number | null;
  coefficients: Record<string, number>;
  intercept: number;
};
export type FISSpec = {
  schema_version: number;
  fis_id: string;
  name: string;
  system_type: "mamdani" | "sugeno";
  inputs: FuzzyVariable[];
  output: FuzzyVariable;
  rules: FuzzyRule[];
  operators: {
    and_operator: "min" | "product" | "lukasiewicz" | "hamacher" | "einstein";
    or_operator:
      "max" | "probabilistic_sum" | "bounded_sum" | "hamacher" | "einstein";
    implication: "min" | "product";
    aggregation:
      "max" | "probabilistic_sum" | "bounded_sum" | "hamacher" | "einstein";
    defuzzification: "centroid";
    centroid_resolution: number;
    centroid_sampling: "inclusive_nodes" | "midpoint_cells";
  };
  semantic_hash: string | null;
};
export type FISTrace = {
  fis_id: string;
  semantic_hash: string;
  input_values: Record<string, number>;
  memberships: Array<{
    variable: string;
    value: number;
    memberships: Record<string, number>;
  }>;
  rules: Array<{
    rule_id: string;
    name: string;
    enabled: boolean;
    connector: string;
    clause_values: Record<string, number>;
    firing_strength: number;
    weight: number;
    weighted_firing_strength: number;
    output_term: string;
    consequent_value: number | null;
  }>;
  output_grid: number[];
  aggregated_membership: number[];
  defuzzification: "centroid";
  output_domain: [number, number] | null;
  centroid_resolution: number | null;
  centroid_sampling: "inclusive_nodes" | "midpoint_cells" | null;
  centroid_dx: number | null;
  centroid_sample_count: number | null;
  final_output: number;
  reconstruction_output: number;
  reconstruction_error: number;
  inference_kind: "mamdani" | "sugeno";
};
export type FISEvaluation = {
  evaluation: { output_name: string; output: number; trace: FISTrace };
  trace_artifact_sha256: string | null;
};
export type ResponseSurface = {
  fis_id: string;
  semantic_hash: string;
  x_variable: string;
  y_variable: string;
  fixed_inputs: Record<string, number>;
  resolution: number;
  samples: Array<{ x: number; y: number; output: number | null }>;
};

export type TrainingEpochPoint = {
  epoch: number;
  train_loss: number;
  validation_loss: number | null;
  train_metrics: Record<string, number>;
  validation_metrics: Record<string, number> | null;
};
export type TrainingRun = {
  schema_version: number;
  run_id: string;
  created_at: string;
  status: "succeeded";
  model_kind: "flat_neuro_fuzzy" | "logistic_regression" | "linear_regression" | "decision_tree" | "random_forest" | "gradient_boosting";
  task: "regression" | "binary_classification";
  target: string;
  dataset_fingerprint: string | null;
  dataset_artifact_sha256: string | null;
  feature_columns: string[];
  seed: number;
  split_seed: number | null;
  training_seed: number | null;
  randomness_protocol: string;
  max_epochs: number;
  learning_rate: number;
  batch_size: number;
  patience: number | null;
  split: {
    family: "random_holdout";
    seed: number;
    split_seed: number | null;
    split_identity: string | null;
    validation_fraction: number;
    test_fraction: number;
    train_count: number;
    validation_count: number;
    test_count: number;
    preprocessing_fit_scope: "train_only";
    test_status: "LOCKED_NOT_EVALUATED";
  };
  model_spec: Record<string, unknown>;
  normalization: Record<string, unknown>;
  training_summary: {
    source: string;
    epochs_ran: number;
    best_epoch: number;
    monitor_name: string;
    best_monitor_value: number;
    train_loss: number;
    train_metrics: Record<string, number>;
    validation_loss: number | null;
    validation_metrics: Record<string, number> | null;
  };
  trajectory: TrainingEpochPoint[];
  validation_metrics: Record<string, number>;
  prediction_preview: Array<{
    row: number;
    target: number;
    prediction: number;
    probability: number | null;
    calibrated_probability?: number | null;
    predicted_label: number | null;
    residual: number | null;
  }>;
  confusion_matrix: {
    true_negative: number;
    false_positive: number;
    false_negative: number;
    true_positive: number;
  } | null;
  calibration: Array<{
    lower: number;
    upper: number;
    count: number;
    mean_probability: number;
    observed_positive_rate: number;
  }>;
  model_artifact_sha256: string;
  runtime_seconds: number;
  evaluation_split: "validation";
  scientific_note: string;
};
