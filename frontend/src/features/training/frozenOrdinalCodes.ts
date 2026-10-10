import type { TrainingRun, TransformPipelineContract } from "../../api";

export function frozenOrdinalCodes(pipeline: TransformPipelineContract | null, run: TrainingRun | null): Record<string, Record<string, number>> {
  if (!pipeline || !run || pipeline.preprocessing_artifact_sha256 !== run.preprocessing_artifact_sha256) return {};
  const step = pipeline.steps.find((item) => item.step_type === "OrdinalEncoder" && item.artifact_identity === run.preprocessing_artifact_sha256);
  const raw = step?.parameters.categories;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const codes: Record<string, Record<string, number>> = {};
  for (const [column, value] of Object.entries(raw)) {
    if (!value || typeof value !== "object" || Array.isArray(value)) continue;
    const entries = Object.entries(value);
    if (!entries.length || entries.some(([, code]) => typeof code !== "number" || !Number.isFinite(code))) continue;
    codes[column] = Object.fromEntries(entries) as Record<string, number>;
  }
  return codes;
}
