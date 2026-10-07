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
  if (input.hasValidationEvaluation) return "Saved validation evaluation";
  if (input.hasTrainingRun) return "Validation analysis ready";
  return "Open analyses workspace";
}

export function evidenceOverviewLabel(hasExactTrace: boolean): string {
  return hasExactTrace ? "Exact trace available" : "Open evidence workspace";
}

export function projectModelOverviewLabel(input: {
  status: ProjectModelOverviewState;
  fisName: string | null;
  trainingModelKind: string | null;
}): string {
  if (input.status === "idle" || input.status === "loading") return "Checking saved models…";
  if (input.status === "error") return "Model state unavailable";
  if (input.fisName) return input.fisName;
  if (input.trainingModelKind) return `Trained ${input.trainingModelKind.replaceAll("_", " ")}`;
  return "No saved model";
}

export function trainingStudyOverviewLabel(input: {
  status: TrainingStudyOverviewState;
  studyName: string | null;
  runCount: number | null;
  hasTrainingRun: boolean;
}): string {
  if (input.status === "idle" || input.status === "loading") {
    return "Checking saved study history…";
  }
  if (input.status === "error") return "Study history unavailable";
  if (input.status === "available") {
    if (input.studyName === null || input.runCount === null) {
      return "Saved study details unavailable";
    }
    return `${input.runCount} runs · ${input.studyName}`;
  }
  return input.hasTrainingRun ? "Training run available" : "No saved study";
}
