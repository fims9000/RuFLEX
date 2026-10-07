import { describe, expect, it } from "vitest";
import { parseFisRunInputs } from "./fisRunInputs";

describe("parseFisRunInputs", () => {
  it("parses finite numeric values by declared input name", () => {
    expect(parseFisRunInputs(["temperature", "torque"], { temperature: " 21.5 ", torque: "-2e1" })).toEqual({
      ok: true,
      values: { temperature: 21.5, torque: -20 },
    });
  });

  it("rejects blank, missing, NaN and infinite values without substituting zero", () => {
    expect(parseFisRunInputs(["blank", "missing", "bad", "infinite"], {
      blank: "  ",
      bad: "not a number",
      infinite: "Infinity",
    })).toEqual({ ok: false, invalidInputs: ["blank", "missing", "bad", "infinite"] });
  });
});
