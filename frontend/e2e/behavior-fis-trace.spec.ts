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

test("Studio authors an exact FIS-bound requirement and recovers a lost creation response", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-behavior-fis-author-${Date.now()}`);
  const api = "http://127.0.0.1:8010/api/projects";
  const created = await page.request.post(api, { data: { path, name: "FIS requirement authoring" } });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session_id as string;
  const confirmed = await page.request.post(`${api}/dataset/confirm`, { data: {
    session_id: sessionId, csv_text: "temperature,target\n10,0\n20,1\n30,1\n40,0\n", target: "target", task: "binary_classification", id_columns: [],
  } });
  expect(confirmed.ok()).toBeTruthy();
  const fisResponse = await page.request.post(`${api}/fis/default`, { data: { session_id: sessionId, name: "Saved FIS source" } });
  expect(fisResponse.ok()).toBeTruthy();
  const fis = await fisResponse.json();
  let writes = 0;
  await page.route("**/api/projects/evidence/behavior-specs", async (route) => {
    writes += 1;
    await route.fetch();
    await route.abort("failed");
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByLabel("Behavior model source")).toHaveValue("fis");
  await expect(page.getByText(`FIS ${fis.name} · exact saved semantic revision ${fis.semantic_hash}`)).toBeVisible();
  await page.getByLabel("Behavior input temperature").fill("");
  await page.getByRole("button", { name: "Create and run BehaviorSpec" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "temperature must be a finite number" })).toBeVisible();
  expect(writes).toBe(0);
  await page.getByLabel("Behavior input temperature").fill("25");
  await page.getByRole("textbox", { name: "Name", exact: true }).fill("Studio FIS range");
  await page.getByLabel("Behavior minimum").fill("");
  await page.getByRole("button", { name: "Create and run BehaviorSpec" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Behavior minimum must be a finite number" })).toBeVisible();
  expect(writes).toBe(0);
  await page.getByLabel("Behavior minimum").fill("2");
  await page.getByLabel("Behavior maximum").fill("3");
  await page.getByRole("button", { name: "Create and run BehaviorSpec" }).click();
  await expect(page.getByTestId("behavior-spec-create-recovery")).toBeVisible();
  await page.getByRole("button", { name: "Retry saved requirement lookup" }).click();
  await expect(page.getByTestId("behavior-spec")).toContainText("FIS-bound requirement");
  await expect(page.getByTestId("behavior-exact-traces")).toContainText("Persisted exact FIS trace");
  expect(writes).toBe(1);
  const specs = await page.request.get(`${api}/${sessionId}/evidence/behavior-specs`);
  expect(specs.ok()).toBeTruthy();
  expect((await specs.json()).filter((item: { name: string }) => item.name === "Studio FIS range")).toHaveLength(1);

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByTestId("behavior-exact-traces")).toContainText("Persisted exact FIS trace");
});
