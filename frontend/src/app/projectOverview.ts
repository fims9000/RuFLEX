export type TrainingStudyOverviewState = "idle" | "loading" | "none" | "available" | "error";
export type ProjectModelOverviewState = "idle" | "loading" | "loaded" | "error";

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
