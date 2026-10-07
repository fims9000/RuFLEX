import { describe, expect, it } from "vitest";
import { assuranceGateSummary } from "./ProjectExplorer";

describe("assuranceGateSummary", () => {
  it("reports each gate outcome instead of describing passed gates as available", () => {
    expect(
      assuranceGateSummary({
        assurance_id: "assurance-1",
        gates: [
          { key: "dataset", status: "PASS", evidence: [], risk: null },
          { key: "integrity", status: "WARN", evidence: [], risk: null },
          { key: "final-test", status: "FAIL", evidence: [], risk: null },
          { key: "calibration", status: "NOT_AVAILABLE", evidence: [], risk: null },
        ],
        claims: [],
        unresolved_risks: [],
        scientific_note: "",
      }),
    ).toBe("1 passed · 1 warnings · 1 failed · 1 unavailable");
  });

  it("keeps zero outcomes explicit for an empty AssuranceCase", () => {
    expect(
      assuranceGateSummary({
        assurance_id: "assurance-empty",
        gates: [],
        claims: [],
        unresolved_risks: [],
        scientific_note: "",
      }),
    ).toBe("0 passed · 0 warnings · 0 failed · 0 unavailable");
  });
});
