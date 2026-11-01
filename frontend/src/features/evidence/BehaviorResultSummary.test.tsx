import "@testing-library/jest-dom/vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { BehaviorSpec, BehaviorSpecResult } from "../../api";
import { BehaviorResultSummary } from "./BehaviorResultSummary";

afterEach(cleanup);
const spec = { spec_id: "a", kind: "output_range", minimum: 0, maximum: 1 } as BehaviorSpec;
const result = { spec_id: "a", status: "PASS", observed_output: .95, detail: "Original raw detail", run_id: "run-a" } as BehaviorSpecResult;
it("shows the observed output and declared limits with a readable range", () => {
  render(<BehaviorResultSummary spec={spec} result={result} />);
  expect(screen.getByRole("img", { name: /allowed range 0 to 1/ })).toBeVisible();
  expect(screen.getByText(/Requirement satisfied for this input/)).toBeVisible();
  expect(screen.getByText("Original raw detail")).not.toBeVisible();
});
it("retains failures and does not label an out-of-range value a pass", () => {
  render(<BehaviorResultSummary spec={spec} result={{ ...result, status: "FAIL", observed_output: 2 }} />);
  expect(screen.getByText(/Requirement violated for this input/)).toBeVisible();
  expect(screen.getByRole("img", { name: /Output 2/ })).toBeVisible();
});
it("does not divide by zero for a constant range", () => {
  render(<BehaviorResultSummary spec={{ ...spec, maximum: 0 }} result={result} />);
  expect(screen.queryByRole("img")).toBeNull();
});
it("refuses to present a different requirement's result", () => {
  render(<BehaviorResultSummary spec={spec} result={{ ...result, spec_id: "other" }} />);
  expect(screen.getByRole("alert")).toBeVisible();
  expect(screen.queryByRole("img")).toBeNull();
});
