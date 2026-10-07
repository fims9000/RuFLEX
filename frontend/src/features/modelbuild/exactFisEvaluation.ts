import { FISEvaluation, FISSpec } from "../../api";

function canonicalNumbers(values: Record<string, number>): string {
  return JSON.stringify(Object.entries(values).sort(([left], [right]) => left.localeCompare(right)));
}

export function exactFisEvaluationMatchesCurrent(
  spec: FISSpec,
  evaluation: FISEvaluation | null,
  runInputs: Record<string, string>,
): boolean {
  if (!evaluation || !spec.semantic_hash) return false;
  const trace = evaluation.evaluation.trace;
  if (trace.fis_id !== spec.fis_id || trace.semantic_hash !== spec.semantic_hash) return false;
  const currentInputs = Object.fromEntries(
    Object.entries(runInputs).map(([name, value]) => [name, Number(value)]),
  );
  return canonicalNumbers(trace.input_values) === canonicalNumbers(currentInputs);
}
