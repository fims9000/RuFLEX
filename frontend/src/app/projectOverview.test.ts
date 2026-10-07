import { describe, expect, it } from "vitest";
import { analysisOverviewLabel, evidenceOverviewLabel, projectModelOverviewLabel, trainingStudyOverviewLabel } from "./projectOverview";

describe("analysisOverviewLabel", () => {
  it("does not infer that all analysis types are absent from a missing latest Evaluation", () => {
    expect(analysisOverviewLabel({ hasValidationEvaluation: false, hasTrainingRun: false })).toBe("Open analyses workspace");
    expect(analysisOverviewLabel({ hasValidationEvaluation: true, hasTrainingRun: false })).toBe("Saved validation evaluation");
    expect(analysisOverviewLabel({ hasValidationEvaluation: false, hasTrainingRun: true })).toBe("Validation analysis ready");
  });
});

describe("evidenceOverviewLabel", () => {
  it("does not infer that the evidence workspace is empty from a missing exact FIS trace", () => {
    expect(evidenceOverviewLabel(false)).toBe("Open evidence workspace");
    expect(evidenceOverviewLabel(true)).toBe("Exact trace available");
  });
});

describe("projectModelOverviewLabel", () => {
  it("keeps model loading and errors distinct from a verified empty project", () => {
    expect(projectModelOverviewLabel({ status: "loading", fisName: null, trainingModelKind: null })).toBe("Checking saved models…");
    expect(projectModelOverviewLabel({ status: "error", fisName: null, trainingModelKind: null })).toBe("Model state unavailable");
  });

  it("shows a persisted FIS or trained model instead of inferring no model", () => {
    expect(projectModelOverviewLabel({ status: "loaded", fisName: "Pump controller", trainingModelKind: "decision_tree" })).toBe("Pump controller");
    expect(projectModelOverviewLabel({ status: "loaded", fisName: null, trainingModelKind: "decision_tree" })).toBe("Trained decision tree");
    expect(projectModelOverviewLabel({ status: "loaded", fisName: null, trainingModelKind: null })).toBe("No saved model");
  });
});

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
