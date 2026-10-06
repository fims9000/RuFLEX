import { DatasetConfirmation, TrainingRun, studioApi } from "../../api";

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  return JSON.stringify(value) ?? "undefined";
}

export function trainingRunMatchesRecovery(
  candidate: TrainingRun,
  pending: { config: Parameters<typeof studioApi.runTraining>[1]; requestedAt: number },
  dataset: DatasetConfirmation | null,
): boolean {
  const config = pending.config;
  const requestedSplitSeed = config.split_seed ?? config.seed;
  const createdAt = Date.parse(candidate.created_at);
  if (!Number.isFinite(createdAt) || createdAt < pending.requestedAt - 10_000) return false;
  if (!dataset || candidate.dataset_fingerprint !== dataset.contract.dataset_fingerprint || candidate.dataset_artifact_sha256 !== dataset.contract.source_artifact_sha256 || candidate.target !== dataset.contract.target || candidate.feature_columns.join("\u0000") !== dataset.contract.feature_columns.join("\u0000")) return false;
  const builtInAdapterByModel: Record<string, string> = {
    flat_neuro_fuzzy: "native_flat_neuro_fuzzy", decision_tree: "native_decision_tree",
    random_forest: "native_random_forest", gradient_boosting: "native_gradient_boosting",
    logistic_regression: "native_linear", linear_regression: "native_linear",
  };
  const resolvedAdapterKey = config.adapter_key ?? builtInAdapterByModel[config.model_kind ?? "flat_neuro_fuzzy"] ?? null;
  if (candidate.model_kind !== config.model_kind || candidate.adapter_key !== resolvedAdapterKey || candidate.seed !== (config.training_seed ?? config.seed) || candidate.training_seed !== (config.training_seed ?? config.seed) || candidate.split_seed !== requestedSplitSeed) return false;
  if (candidate.split.split_contract_id !== (config.split_contract_id ?? null) || candidate.split.validation_fraction !== config.validation_fraction || candidate.split.test_fraction !== config.test_fraction) return false;
  const declared = candidate.declared_training_config;
  return declared?.schema_version === 1
    && declared.model_kind === candidate.model_kind
    && declared.adapter_key === candidate.adapter_key
    && declared.adapter_version === (candidate.adapter_version ?? null)
    && canonicalJson(declared.parameters) === canonicalJson(config);
}
