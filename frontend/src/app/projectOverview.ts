import { ui } from "../design/language";

export type TrainingStudyOverviewState = "idle" | "loading" | "none" | "available" | "error";
export type ProjectModelOverviewState = "idle" | "loading" | "loaded" | "error";
export type ProjectStudyNextStep = "CHECKING" | "UNAVAILABLE" | "TRAIN" | "OPEN_SAVED_STUDY" | "NONE";

export function projectStudyNextStep(input: {
  status: TrainingStudyOverviewState;
  hasStudy: boolean;
  hasTrainingRun: boolean;
}): ProjectStudyNextStep {
  if (input.hasTrainingRun) return "NONE";
  if (input.status === "idle" || input.status === "loading") return "CHECKING";
  if (input.status === "error") return "UNAVAILABLE";
  if (input.status === "available") return input.hasStudy ? "OPEN_SAVED_STUDY" : "CHECKING";
  return input.hasStudy ? "CHECKING" : "TRAIN";
}

export function analysisOverviewLabel(input: {
  hasValidationEvaluation: boolean;
  hasTrainingRun: boolean;
}): string {
  if (input.hasValidationEvaluation) return ui("Saved validation evaluation", "Оценка на валидации сохранена");
  if (input.hasTrainingRun) return ui("Validation analysis ready", "Можно оценить модель");
  return ui("Open analyses workspace", "Открыть анализ");
}

export function evidenceOverviewLabel(hasExactTrace: boolean): string {
  return hasExactTrace ? ui("Exact trace available", "Точный расчёт сохранён") : ui("Open evidence workspace", "Открыть доказательства");
}

export function projectModelOverviewLabel(input: {
  status: ProjectModelOverviewState;
  fisName: string | null;
  trainingModelKind: string | null;
}): string {
  if (input.status === "idle" || input.status === "loading") return ui("Checking saved models…", "Проверка моделей…");
  if (input.status === "error") return ui("Model state unavailable", "Состояние моделей недоступно");
  if (input.fisName) return input.fisName;
  if (input.trainingModelKind) return ui(`Trained ${input.trainingModelKind.replaceAll("_", " ")}`, `Обучена ${input.trainingModelKind.replaceAll("_", " ")}`);
  return ui("No saved model", "Нет сохранённой модели");
}

export function trainingStudyOverviewLabel(input: {
  status: TrainingStudyOverviewState;
  studyName: string | null;
  runCount: number | null;
  hasTrainingRun: boolean;
}): string {
  if (input.status === "idle" || input.status === "loading") {
    return ui("Checking saved study history…", "Проверка сохранённых экспериментов…");
  }
  if (input.status === "error") return ui("Study history unavailable", "История экспериментов недоступна");
  if (input.status === "available") {
    if (input.studyName === null || input.runCount === null) {
      return ui("Saved study details unavailable", "Данные эксперимента недоступны");
    }
    return ui(`${input.runCount} runs · ${input.studyName}`, `${input.runCount} запусков · ${input.studyName}`);
  }
  return input.hasTrainingRun ? ui("Training run available", "Есть обученная модель") : ui("No saved study", "Нет экспериментов");
}
