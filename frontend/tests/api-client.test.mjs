import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("Studio client defaults to the local FastAPI endpoint", async () => {
  const source = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");
  const declaration = source.match(/^const apiBase\s*=\s*import\.meta\.env\.VITE_RUFLEX_API_URL\s*\?\?\s*"([^"]+)"/m);
  assert.ok(declaration, "The client must preserve the configurable API URL and explicit local fallback.");
  assert.equal(declaration[1], "http://127.0.0.1:8010");
});
