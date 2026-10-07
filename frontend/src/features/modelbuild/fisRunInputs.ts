export type FisRunInputParseResult =
  | { ok: true; values: Record<string, number> }
  | { ok: false; invalidInputs: string[] };

export function parseFisRunInputs(
  inputNames: readonly string[],
  rawInputs: Record<string, string>,
): FisRunInputParseResult {
  const values: Record<string, number> = {};
  const invalidInputs: string[] = [];
  for (const name of inputNames) {
    const raw = rawInputs[name]?.trim() ?? "";
    const value = raw === "" ? Number.NaN : Number(raw);
    if (!Number.isFinite(value)) invalidInputs.push(name);
    else values[name] = value;
  }
  return invalidInputs.length
    ? { ok: false, invalidInputs }
    : { ok: true, values };
}
