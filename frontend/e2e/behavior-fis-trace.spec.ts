import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("FIS-bound BehaviorSpec failure reopens with its exact persisted trace", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-behavior-fis-trace-${Date.now()}`);
  const api = "http://127.0.0.1:8010/api/projects";
  const created = await page.request.post(api, { data: { path, name: "Traced FIS behavior" } });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session_id as string;
  const confirmed = await page.request.post(`${api}/dataset/confirm`, { data: {
    session_id: sessionId, csv_text: "temperature,target\n10,0\n20,1\n30,1\n40,0\n", target: "target", task: "binary_classification", id_columns: [],
  } });
  expect(confirmed.ok()).toBeTruthy();
  const fisResponse = await page.request.post(`${api}/fis/default`, { data: { session_id: sessionId, name: "FIS with behavior trace" } });
  expect(fisResponse.ok()).toBeTruthy();
  const fis = await fisResponse.json();
  const specResponse = await page.request.post(`${api}/evidence/behavior-specs`, { data: {
    session_id: sessionId, fis_id: fis.fis_id, name: "Impossible FIS range", kind: "output_range",
    sample: { temperature: 25 }, minimum: 2, maximum: 3, rationale: "Inspect an exact failed computation.",
  } });
  expect(specResponse.ok()).toBeTruthy();
  const spec = await specResponse.json();
  const resultResponse = await page.request.post(`${api}/evidence/behavior-specs/run`, { data: { session_id: sessionId, spec_id: spec.spec_id } });
  expect(resultResponse.ok()).toBeTruthy();
  const result = await resultResponse.json();
  expect(result.status).toBe("FAIL");
  expect(result.exact_fis_traces.primary.input_values).toEqual({ temperature: 25 });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByTestId("behavior-counterexample")).toContainText("Expected: output in [2, 3]");
  await expect(page.getByTestId("behavior-exact-traces")).toContainText("Persisted exact FIS trace");
  await page.getByText(/Primary input · exact FIS computation/).click();
  await expect(page.getByTestId("behavior-exact-trace")).toContainText("temperature");
  await expect(page.getByTestId("behavior-exact-trace")).toContainText("reconstruction error");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByTestId("behavior-exact-traces")).toContainText("Persisted exact FIS trace");
});
