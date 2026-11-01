import { expect, it } from "vitest";
import { learningDatasets, learningDatasetHashes, learningDatasetForHash } from "./learningDatasets";

it("declares small deterministic wider fixtures with explicit targets and identity", async () => {
  expect(learningDatasets.map((d) => d.id)).toEqual(["soil", "equipment", "energy"]);
  for (const d of learningDatasets) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(d.csv));
    expect(Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")).toBe(learningDatasetHashes[d.id]);
    expect(learningDatasetForHash(learningDatasetHashes[d.id])?.id).toBe(d.id);
    const rows = d.csv.trim().split("\n").map((line) => line.split(","));
    expect(rows.length - 1).toBe(d.rows);
    expect(rows[0].length).toBe(d.features + 2);
    expect(rows[0].at(-1)).toBe(d.target);
    expect(rows.every((row) => row.length === rows[0].length)).toBe(true);
    expect(new Set(rows.slice(1).map((row) => row[0])).size).toBe(d.rows);
    expect(d.features).toBeGreaterThanOrEqual(8);
    if (d.task === "binary_classification") expect([...new Set(rows.slice(1).map((r) => r.at(-1)))].sort()).toEqual(["0", "1"]);
  }
});

it("does not call changed or unknown data a registered synthetic fixture", () => {
  expect(learningDatasetForHash("changed")).toBeUndefined();
  expect(learningDatasetForHash(undefined)).toBeUndefined();
});
