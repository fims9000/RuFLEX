/** Preserve visibly nonzero evidence when fixed-decimal rounding would say zero. */
export function formatEvidenceNumber(value: number, decimals = 4): string {
  if (!Number.isFinite(value)) return "N/A";
  const fixed = value.toFixed(decimals);
  return value !== 0 && Number(fixed) === 0 ? value.toExponential(3) : fixed;
}
