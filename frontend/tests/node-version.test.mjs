import { strict as assert } from "node:assert";
import { test } from "node:test";
import { supportsNode } from "../scripts/check-node-version.mjs";

test("release tooling accepts the supported Node branch boundaries", () => {
  for (const version of ["22.22.2", "22.23.0", "24.15.0", "24.16.0", "26.0.0", "v26.12.0", "28.0.0"]) assert.equal(supportsNode(version), true, version);
});

test("release tooling rejects older and malformed Node versions before startup", () => {
  for (const version of ["20.19.0", "22.22.1", "24.14.9", "23.0.0", "25.0.0", "garbage", "26", "26..0", "26.0.", "26.0.0-beta", "26.0.NaN", "-1.0.0"]) assert.equal(supportsNode(version), false, version);
});
