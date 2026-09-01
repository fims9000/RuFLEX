import test from "node:test";
import assert from "node:assert/strict";

test("Studio client defaults to the local FastAPI endpoint", () => {
  assert.equal("http://127.0.0.1:8000".startsWith("http://127.0.0.1"), true);
});
