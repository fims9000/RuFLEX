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
import { ui } from "../design/language";

type ObjectTarget = "DATA" | "MODELS" | "STUDIES" | "ANALYSES" | "EVIDENCE";

export function assuranceGateSummary(assurance: AssuranceCase): string {
  const counts = assurance.gates.reduce(
    (summary, gate) => {
      summary[gate.status] += 1;
      return summary;
    },
    { PASS: 0, WARN: 0, FAIL: 0, NOT_AVAILABLE: 0 },
  );
  return ui(`${counts.PASS} passed · ${counts.WARN} warnings · ${counts.FAIL} failed · ${counts.NOT_AVAILABLE} unavailable`, `${counts.PASS} пройдено · ${counts.WARN} предупреждений · ${counts.FAIL} ошибок · ${counts.NOT_AVAILABLE} недоступно`);
}

export function ProjectExplorer({
  projectName,
  emptyProjectVerified = false,
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
  emptyProjectVerified?: boolean;
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
  const hasSavedObjects = Boolean(dataset || fis || trainingRun || trainingStudy || stabilityAnalysis || stabilityGatePolicy || evaluation || analysisEvaluation || analysisComparison || calibrationTransform || decisionThreshold || finalTestEvaluation || sliceAnalysis || generalization || treeEvidence || explanation || explanationCheck || behaviorResult || reproducibility || exhaustive || assurance || expertCorrection || traceCount);
  const hasReadError = stabilityAnalysisHydrationStatus === "error" || evaluationStatus === "error" || treeEvidenceHydrationStatus === "error";
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
      {!projectName && (
        <div className="tree-subtitle">{ui("No project open", "Проект не открыт")}</div>
      )}
      {projectName && emptyProjectVerified && !hasSavedObjects && !hasReadError && <p className="tree-empty">{ui("No saved objects yet", "Сохранённых объектов пока нет")}</p>}
      {dataset && <section>
        <strong>{ui("DATA", "ДАННЫЕ")}</strong>
        {item("DATA", dataset.contract.target, ui(`${dataset.profile.row_count} rows`, `${dataset.profile.row_count} строк`))}
      </section>}
      {(dataset || fis || trainingRun || expertCorrection) && <section>
        <strong>{ui("MODELS", "МОДЕЛИ")}</strong>
        {fis ? (
          item("MODELS", fis.name, fis.system_type)
        ) : dataset ? (
          item("MODELS", ui("New FIS from dataset", "Новая нечёткая модель"), ui("create model", "создать модель"))
        ) : null}
        {trainingRun &&
          item(
            "MODELS",
            `${trainingRun.model_kind === "flat_neuro_fuzzy" ? "ANFIS" : trainingRun.model_kind === "decision_tree" ? "Decision Tree" : trainingRun.model_kind === "random_forest" ? "Random Forest" : trainingRun.model_kind === "gradient_boosting" ? "Gradient Boosting" : trainingRun.model_kind === "logistic_regression" ? "Logistic Regression" : trainingRun.model_kind === "linear_regression" ? "Linear Regression" : trainingRun.model_kind === "mlp" ? "MLP" : trainingRun.model_kind} ${trainingRun.run_id.slice(0, 8)}`,
            ui("trained revision", "обученная версия"),
          )}
        {expertCorrection && item(
          "MODELS",
          ui("Expert correction", "Экспертная правка"),
          ui(`${expertCorrection.fitted_rule_ids.length} consequents · ${expertCorrection.test_status}`, `${expertCorrection.fitted_rule_ids.length} заключений · ${expertCorrection.test_status}`),
        )}
      </section>}
      {(trainingStudy || trainingRun || stabilityAnalysis || stabilityAnalysisHydrationStatus === "error") && <section>
        <strong>{ui("STUDIES", "ЭКСПЕРИМЕНТЫ")}</strong>
        {trainingStudy ? (
          <div className="object-tree-study">
            {item(
              "STUDIES",
              trainingStudy.name,
              ui(`${trainingStudy.seed_runs.length} seed runs`, `${trainingStudy.seed_runs.length} запусков`),
            )}
            <div className="object-tree-children" aria-label={ui(`${trainingStudy.name} seed runs`, `${trainingStudy.name}: запуски`)}>
              <small>{ui("Trial · declared validation selection", "Эксперимент · выбор по валидации")}</small>
              {trainingStudy.seed_runs.map((run) => (
                <button
                  key={run.run_id}
                  className="object-tree-child"
                  onClick={() => onSelect("STUDIES")}
                >
                  <span>{ui(`SeedRun split ${run.split_seed ?? run.split.split_seed} · train ${run.training_seed ?? run.seed}`, `Разбиение ${run.split_seed ?? run.split.split_seed} · обучение ${run.training_seed ?? run.seed}`)}</span>
                  <small>{run.run_id === trainingStudy.selected_run_id ? ui("selected", "выбран") : run.status}</small>
                </button>
              ))}
            </div>
          </div>
        ) : trainingRun ? (
          item(
            "STUDIES",
            ui(`Training run ${trainingRun.run_id.slice(0, 8)}`, `Обучение ${trainingRun.run_id.slice(0, 8)}`),
            ui(`${trainingRun.trajectory.length} epochs`, `${trainingRun.trajectory.length} эпох`),
          )
        ) : null}
        {stabilityAnalysis && item("STUDIES", ui("Study Stability Analysis", "Анализ устойчивости"), ui(`${stabilityAnalysis.case_count} validation cases · HCIR ${stabilityAnalysis.high_confidence_instability_rate === null ? "N/A" : `${(stabilityAnalysis.high_confidence_instability_rate * 100).toFixed(1)}%`}`, `${stabilityAnalysis.case_count} случаев валидации · HCIR ${stabilityAnalysis.high_confidence_instability_rate === null ? "Н/Д" : `${(stabilityAnalysis.high_confidence_instability_rate * 100).toFixed(1)}%`}`))}
        {!stabilityAnalysis && stabilityAnalysisHydrationStatus === "error" && <div className="tree-empty" role="alert"><span>{ui("Saved stability analysis lookup unavailable.", "Анализ устойчивости недоступен.")} {stabilityAnalysisHydrationError}</span><button onClick={onRetryStabilityAnalysis}>{ui("Retry stability check", "Повторить проверку")}</button></div>}
      </section>}
      {(analysisEvaluation || stabilityGatePolicy || analysisComparison || calibrationTransform || decisionThreshold || finalTestEvaluation || sliceAnalysis || generalization) && <section>
        <strong>{ui("ANALYSES", "АНАЛИЗ")}</strong>
        {analysisEvaluation && item("ANALYSES", ui("Validation evaluation", "Оценка на валидации"), ui(`${Object.keys(analysisEvaluation.metrics).length} metrics`, `${Object.keys(analysisEvaluation.metrics).length} метрик`))}
        {stabilityGatePolicy && item("ANALYSES", ui("Stability-Aware Review Gate", "Порог проверки устойчивости"), ui(`${stabilityGatePolicy.decisions.filter((item) => item.disposition === "REVIEW").length} REVIEW`, `${stabilityGatePolicy.decisions.filter((item) => item.disposition === "REVIEW").length} на проверку`))}
        {analysisComparison && item("ANALYSES", ui("Model comparison", "Сравнение моделей"), ui(`${analysisComparison.metric_rows.length} subjects`, `${analysisComparison.metric_rows.length} объекта`))}
        {calibrationTransform && item("ANALYSES", ui("Calibration transform", "Калибровка"), `${calibrationTransform.method} · ${ui("validation", "валидация")}`)}
        {decisionThreshold && item("ANALYSES", ui("Decision threshold", "Порог решения"), `${decisionThreshold.selected_threshold.toFixed(2)} · ${decisionThreshold.probability_source}`)}
        {finalTestEvaluation && item("ANALYSES", ui("Final-test evaluation", "Оценка на финальном тесте"), ui(`${finalTestEvaluation.test_row_count} rows · frozen policy`, `${finalTestEvaluation.test_row_count} строк · правило зафиксировано`))}
        {sliceAnalysis && item("ANALYSES", ui("Slice analysis", "Анализ срезов"), ui(`${sliceAnalysis.results.length} slices · ${sliceAnalysis.metric}`, `${sliceAnalysis.results.length} срезов · ${sliceAnalysis.metric}`))}
        {generalization && item("ANALYSES", ui("Generalization contract", "Область применимости"), generalization.contract.frozen_at ? ui("frozen", "зафиксирована") : ui("draft", "черновик"))}
      </section>}
      {(evaluation || treeEvidence || explanation || explanationCheck || behaviorResult || reproducibility || exhaustive || assurance || traceCount > 1 || evaluationStatus === "error" || treeEvidenceHydrationStatus === "error") && <section>
        <strong>{ui("EVIDENCE", "ДОКАЗАТЕЛЬСТВА")}</strong>
        {evaluation ? (
          item("EVIDENCE", ui("Exact trace", "Точный расчёт"), evaluation.evaluation.output_name)
        ) : evaluationStatus === "error" ? (
          <div className="tree-empty" role="alert"><span>{ui("Saved trace lookup unavailable.", "Сохранённый расчёт недоступен.")} {evaluationError}</span><button onClick={onRetryEvaluation}>{ui("Retry trace check", "Повторить проверку")}</button></div>
        ) : null}
        {treeEvidence && item("EVIDENCE", ui("Exact tree path", "Путь дерева"), ui(`leaf ${treeEvidence.leaf_id}`, `лист ${treeEvidence.leaf_id}`))}
        {!treeEvidence && treeEvidenceHydrationStatus === "error" && <div className="tree-empty" role="alert"><span>{ui("Saved tree-path lookup unavailable.", "Путь дерева недоступен.")} {treeEvidenceHydrationError}</span><button onClick={onRetryTreeEvidence}>{ui("Retry tree-path check", "Повторить проверку")}</button></div>}
        {explanation && item("EVIDENCE", ui(`Post-hoc ${explanation.family.replaceAll("_", " ")}`, `Объяснение ${explanation.family.replaceAll("_", " ")}`), explanation.epistemic_category)}
        {explanationCheck && item("EVIDENCE", ui("Explanation check", "Проверка объяснения"), explanationCheck.status)}
        {behaviorResult && item("EVIDENCE", ui("BehaviorSpec run", "Проверка поведения"), ui(`${behaviorResult.status} · revision bound`, `${behaviorResult.status} · версия зафиксирована`))}
        {reproducibility && item("EVIDENCE", ui("Explanation reproducibility", "Воспроизводимость объяснений"), ui(`${reproducibility.run_ids.length} runs · paired`, `${reproducibility.run_ids.length} запусков · попарно`))}
        {exhaustive && item("EVIDENCE", "Exhaustive Lab", exhaustive.exactness_label)}
        {assurance && item("EVIDENCE", "AssuranceCase", assuranceGateSummary(assurance))}
        {traceCount > 1 && (
          <small className="tree-count">{ui(`${traceCount} persisted traces`, `${traceCount} сохранённых расчётов`)}</small>
        )}
      </section>}
    </div>
  );
}
