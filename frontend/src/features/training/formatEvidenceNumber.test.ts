import { describe, expect, it } from "vitest";
import { formatEvidenceNumber } from "./formatEvidenceNumber";

describe("formatEvidenceNumber", () => {
  it("does not display a small nonzero metric or residual as zero", () => {
    expect(formatEvidenceNumber(5.536504392537577e-15)).toBe("5.537e-15");
    expect(formatEvidenceNumber(-3e-29, 5)).toBe("-3.000e-29");
  });

  it("keeps exact zero, ordinary values and undefined numerical evidence distinct", () => {
    expect(formatEvidenceNumber(0)).toBe("0.0000");
    expect(formatEvidenceNumber(0.31234)).toBe("0.3123");
    expect(formatEvidenceNumber(Number.NaN)).toBe("N/A");
  });
});
