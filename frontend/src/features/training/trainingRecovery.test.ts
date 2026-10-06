import { describe, expect, it } from "vitest";
import { DatasetConfirmation, TrainingRun, studioApi } from "../../api";
import { trainingRunMatchesRecovery } from "./trainingRecovery";

const config: Parameters<typeof studioApi.runTraining>[1] = {
  model_kind: "decision_tree",
  adapter_key: "native_decision_tree",
  seed: 42,
  training_seed: 42,
  split_seed: 42,
  split_contract_id: "split-1",
  rigor_profile: "CONFIRMATORY",
  max_epochs: 20,
  learning_rate: 0.01,
  batch_size: 32,
  patience: 8,
  validation_fraction: 0.2,
  test_fraction: 0.2,
  max_rules: 8,
  n_estimators: 25,
  max_depth: 2,
};
const dataset = {
  contract: {
    dataset_fingerprint: "dataset-fingerprint",
    source_artifact_sha256: "dataset-sha",
    target: "target",
    feature_columns: ["x"],
  },
} as DatasetConfirmation;
const requestedAt = Date.now();

function candidate(parameters: typeof config | Record<string, unknown> = config): TrainingRun {
  return {
    created_at: new Date(requestedAt + 100).toISOString(),
    model_kind: "decision_tree",
    adapter_key: "native_decision_tree",
    adapter_version: "1",
    seed: 42,
    training_seed: 42,
    split_seed: 42,
    dataset_fingerprint: "dataset-fingerprint",
    dataset_artifact_sha256: "dataset-sha",
    target: "target",
    feature_columns: ["x"],
    split: { split_contract_id: "split-1", validation_fraction: 0.2, test_fraction: 0.2 },
    declared_training_config: {
      schema_version: 1,
      model_kind: "decision_tree",
      adapter_key: "native_decision_tree",
      adapter_version: "1",
      parameters,
    },
  } as TrainingRun;
}

describe("training response recovery identity", () => {
  it("accepts a run only when its persisted declared config exactly matches", () => {
    expect(trainingRunMatchesRecovery(candidate(), { config, requestedAt }, dataset)).toBe(true);
  });

  it("rejects a same-seed tree with different max_depth and legacy runs without config", () => {
    expect(trainingRunMatchesRecovery(candidate({ ...config, max_depth: 3 }), { config, requestedAt }, dataset)).toBe(false);
    const legacy = candidate();
    delete legacy.declared_training_config;
    expect(trainingRunMatchesRecovery(legacy, { config, requestedAt }, dataset)).toBe(false);
  });
});
