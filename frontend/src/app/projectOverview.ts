export type TrainingStudyOverviewState = "idle" | "loading" | "none" | "available" | "error";

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
