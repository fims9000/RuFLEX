import {
  AnalysisEvaluation,
  AnalysisComparison,
  CalibrationTransform,
  DecisionThresholdPolicy,
  FinalTestEvaluation,
  ExplanationCheck,
  ExplanationContract,
  BehaviorSpecResult,
  ExplanationReproducibilityAnalysis,
  ExhaustiveLabResult,
  AssuranceCase,
  ExpertCorrectionRevision,
  ArtifactRecord,
  DatasetState,
  FISEvaluation,
  FISSpec,
  GeneralizationResponse,
  SliceAnalysis,
  TrainingRun,
  TrainingStudy,
  StudyStabilityAnalysis,
  StabilityGatePolicy,
  TreePathEvidence,
} from "../api";

type ObjectTarget = "DATA" | "MODELS" | "STUDIES" | "ANALYSES" | "EVIDENCE";

export function ProjectExplorer({
  projectName,
  dataset,
  fis,
  trainingRun,
  trainingStudy,
  stabilityAnalysis,
  stabilityAnalysisHydrationStatus = "available",
  stabilityAnalysisHydrationError,
  onRetryStabilityAnalysis,
  stabilityGatePolicy,
  evaluation,
  evaluationStatus = "available",
  evaluationError = null,
  onRetryEvaluation = () => undefined,
  analysisEvaluation,
  analysisComparison,
  calibrationTransform,
  decisionThreshold,
  finalTestEvaluation,
  sliceAnalysis,
  generalization,
  treeEvidence,
  treeEvidenceHydrationStatus = "available",
  treeEvidenceHydrationError,
  onRetryTreeEvidence,
  explanation,
  explanationCheck,
  behaviorResult,
  reproducibility,
  exhaustive,
  assurance,
  expertCorrection,
  artifacts,
  selected,
  onSelect,
}: {
  projectName?: string;
  dataset: DatasetState | null;
  fis: FISSpec | null;
  trainingRun: TrainingRun | null;
  trainingStudy: TrainingStudy | null;
  stabilityAnalysis: StudyStabilityAnalysis | null;
  stabilityAnalysisHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  stabilityAnalysisHydrationError?: string | null;
  onRetryStabilityAnalysis?: () => void;
  stabilityGatePolicy: StabilityGatePolicy | null;
  evaluation: FISEvaluation | null;
  evaluationStatus?: "idle" | "loading" | "none" | "available" | "error";
  evaluationError?: string | null;
  onRetryEvaluation?: () => void;
  analysisEvaluation: AnalysisEvaluation | null;
  analysisComparison: AnalysisComparison | null;
  calibrationTransform: CalibrationTransform | null;
  decisionThreshold: DecisionThresholdPolicy | null;
  finalTestEvaluation: FinalTestEvaluation | null;
  sliceAnalysis: SliceAnalysis | null;
  generalization: GeneralizationResponse | null;
  treeEvidence: TreePathEvidence | null;
  treeEvidenceHydrationStatus?: "idle" | "loading" | "none" | "available" | "error";
  treeEvidenceHydrationError?: string | null;
  onRetryTreeEvidence?: () => void;
  explanation: ExplanationContract | null;
  explanationCheck: ExplanationCheck | null;
  behaviorResult: BehaviorSpecResult | null;
  reproducibility: ExplanationReproducibilityAnalysis | null;
  exhaustive: ExhaustiveLabResult | null;
  assurance: AssuranceCase | null;
  expertCorrection: ExpertCorrectionRevision | null;
  artifacts: ArtifactRecord[];
  selected: string;
  onSelect: (target: ObjectTarget) => void;
}) {
  const traceCount = artifacts.filter(
    (artifact) =>
      artifact.media_type === "application/vnd.ruflex.fis-trace+json",
  ).length;
  const item = (target: ObjectTarget, label: string, detail?: string) => (
    <button
      className={
        selected === target ? "object-tree-item selected" : "object-tree-item"
      }
      onClick={() => onSelect(target)}
    >
      <span>{label}</span>
      {detail && <small>{detail}</small>}
    </button>
  );
  return (
    <div className="project-object-tree">
      {projectName ? (
        <>
          <div className="project-tree">
            <span className="tree-dot">◆</span>
            <span>{projectName}</span>
          </div>
          <div className="tree-subtitle">canonical project objects</div>
        </>
      ) : (
        <div className="tree-subtitle">No project open</div>
      )}
      <section>
        <strong>DATA</strong>
        {dataset ? (
          item(
            "DATA",
            dataset.contract.target,
            `${dataset.profile.row_count} rows`,
          )
        ) : (
          <span className="tree-empty">No dataset yet</span>
        )}
      </section>
      <section>
        <strong>MODELS</strong>
        {fis ? (
          item("MODELS", fis.name, fis.system_type)
        ) : dataset ? (
          item("MODELS", "New FIS from dataset", "create model")
        ) : (
          <span className="tree-empty">Confirm data to create a model</span>
        )}
        {trainingRun &&
          item(
            "MODELS",
            `${trainingRun.model_kind === "flat_neuro_fuzzy" ? "ANFIS" : trainingRun.model_kind === "decision_tree" ? "Decision Tree" : trainingRun.model_kind === "random_forest" ? "Random Forest" : trainingRun.model_kind === "gradient_boosting" ? "Gradient Boosting" : trainingRun.model_kind === "logistic_regression" ? "Logistic Regression" : "Linear Regression"} ${trainingRun.run_id.slice(0, 8)}`,
            "trained revision",
          )}
        {expertCorrection && item(
          "MODELS",
          "Expert correction",
          `${expertCorrection.fitted_rule_ids.length} consequents · ${expertCorrection.test_status}`,
        )}
      </section>
      <section>
        <strong>STUDIES</strong>
        {trainingStudy ? (
          <div className="object-tree-study">
            {item(
              "STUDIES",
              trainingStudy.name,
              `${trainingStudy.seed_runs.length} seed runs`,
            )}
            <div className="object-tree-children" aria-label={`${trainingStudy.name} seed runs`}>
              <small>Trial · declared validation selection</small>
              {trainingStudy.seed_runs.map((run) => (
                <button
                  key={run.run_id}
                  className="object-tree-child"
                  onClick={() => onSelect("STUDIES")}
                >
                  <span>SeedRun {run.seed}</span>
                  <small>{run.run_id === trainingStudy.selected_run_id ? "selected" : run.status}</small>
                </button>
              ))}
            </div>
          </div>
        ) : trainingRun ? (
          item(
            "STUDIES",
            `Training run ${trainingRun.run_id.slice(0, 8)}`,
            `${trainingRun.trajectory.length} epochs`,
          )
        ) : (
          <span className="tree-empty">No studies yet</span>
        )}
        {stabilityAnalysis && item("STUDIES", "Study Stability Analysis", `${stabilityAnalysis.case_count} validation cases · HCIR ${stabilityAnalysis.high_confidence_instability_rate === null ? "N/A" : `${(stabilityAnalysis.high_confidence_instability_rate * 100).toFixed(1)}%`}`)}
        {!stabilityAnalysis && (stabilityAnalysisHydrationStatus === "idle" || stabilityAnalysisHydrationStatus === "loading") && <span className="tree-empty">Checking saved stability analyses…</span>}
        {!stabilityAnalysis && stabilityAnalysisHydrationStatus === "error" && <div className="tree-empty" role="alert"><span>Saved stability analysis lookup unavailable. {stabilityAnalysisHydrationError}</span><button onClick={onRetryStabilityAnalysis}>Retry stability check</button></div>}
      </section>
      <section>
        <strong>ANALYSES</strong>
        {analysisEvaluation ? (
          item("ANALYSES", "Validation evaluation", `${Object.keys(analysisEvaluation.metrics).length} metrics`)
        ) : trainingRun ? (
          item("ANALYSES", "Unsaved validation analysis", trainingRun.task)
        ) : (
          <span className="tree-empty">No analyses yet</span>
        )}
        {stabilityGatePolicy && item("ANALYSES", "Stability-Aware Review Gate", `${stabilityGatePolicy.decisions.filter((item) => item.disposition === "REVIEW").length} REVIEW`)}
        {analysisComparison && item("ANALYSES", "Model comparison", `${analysisComparison.metric_rows.length} subjects`)}
        {calibrationTransform && item("ANALYSES", "Calibration transform", `${calibrationTransform.method} · validation`)}
        {decisionThreshold && item("ANALYSES", "Decision threshold", `${decisionThreshold.selected_threshold.toFixed(2)} · ${decisionThreshold.probability_source}`)}
        {finalTestEvaluation && item("ANALYSES", "Final-test evaluation", `${finalTestEvaluation.test_row_count} rows · frozen policy`)}
        {sliceAnalysis && item("ANALYSES", "Slice analysis", `${sliceAnalysis.results.length} slices · ${sliceAnalysis.metric}`)}
        {generalization && item("ANALYSES", "Generalization contract", generalization.contract.frozen_at ? "frozen" : "draft")}
      </section>
      <section>
        <strong>EVIDENCE</strong>
        {evaluation ? (
          item("EVIDENCE", `Exact trace`, evaluation.evaluation.output_name)
        ) : evaluationStatus === "loading" || evaluationStatus === "idle" ? (
          <span className="tree-empty">Checking saved exact traces…</span>
        ) : evaluationStatus === "error" ? (
          <div className="tree-empty" role="alert"><span>Saved trace lookup unavailable. {evaluationError}</span><button onClick={onRetryEvaluation}>Retry trace check</button></div>
        ) : (
          <span className="tree-empty">No exact trace evidence yet</span>
        )}
        {treeEvidence && item("EVIDENCE", "Exact tree path", `leaf ${treeEvidence.leaf_id}`)}
        {!treeEvidence && (treeEvidenceHydrationStatus === "idle" || treeEvidenceHydrationStatus === "loading") && <span className="tree-empty">Checking saved tree paths…</span>}
        {!treeEvidence && treeEvidenceHydrationStatus === "error" && <div className="tree-empty" role="alert"><span>Saved tree-path lookup unavailable. {treeEvidenceHydrationError}</span><button onClick={onRetryTreeEvidence}>Retry tree-path check</button></div>}
        {explanation && item("EVIDENCE", `Post-hoc ${explanation.family.replaceAll("_", " ")}`, explanation.epistemic_category)}
        {explanationCheck && item("EVIDENCE", "Explanation check", explanationCheck.status)}
        {behaviorResult && item("EVIDENCE", "BehaviorSpec run", `${behaviorResult.status} · revision bound`)}
        {reproducibility && item("EVIDENCE", "Explanation reproducibility", `${reproducibility.run_ids.length} runs · paired`)}
        {exhaustive && item("EVIDENCE", "Exhaustive Lab", exhaustive.exactness_label)}
        {assurance && item("EVIDENCE", "AssuranceCase", `${assurance.gates.filter((gate) => gate.status === "PASS").length}/${assurance.gates.length} gates available`)}
        {traceCount > 1 && (
          <small className="tree-count">{traceCount} persisted traces</small>
        )}
      </section>
    </div>
  );
}
