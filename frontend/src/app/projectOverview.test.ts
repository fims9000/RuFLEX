import { describe, expect, it } from "vitest";
import { trainingStudyOverviewLabel } from "./projectOverview";

describe("trainingStudyOverviewLabel", () => {
  it("does not claim the project has no studies while history is loading or unavailable", () => {
    expect(trainingStudyOverviewLabel({ status: "loading", studyName: null, runCount: null, hasTrainingRun: false })).toBe("Checking saved study history…");
    expect(trainingStudyOverviewLabel({ status: "error", studyName: null, runCount: null, hasTrainingRun: false })).toBe("Study history unavailable");
  });

  it("summarizes a persisted study even when there is no active TrainingRun", () => {
    expect(trainingStudyOverviewLabel({ status: "available", studyName: "Seed study", runCount: 5, hasTrainingRun: false })).toBe("5 runs · Seed study");
  });

  it("distinguishes an individual run from an absent study", () => {
    expect(trainingStudyOverviewLabel({ status: "none", studyName: null, runCount: null, hasTrainingRun: true })).toBe("Training run available");
    expect(trainingStudyOverviewLabel({ status: "none", studyName: null, runCount: null, hasTrainingRun: false })).toBe("No saved study");
  });
});
