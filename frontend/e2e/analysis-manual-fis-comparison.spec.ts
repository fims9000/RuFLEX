import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("one frozen TrainingRun and one saved manual FIS form a persisted validation comparison", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-manual-fis-comparison-${Date.now()}`);
  const api = "http://127.0.0.1:8010/api/projects";
  const created = await page.request.post(api, { data: { path, name: "One run and FIS" } });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session_id as string;
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 80; index += 1) {
    const temperature = 8 + index * 0.55;
    const torque = 12 + (index * 13) % 75;
    rows.push(`${temperature.toFixed(2)},${torque},${temperature + torque > 64 ? 1 : 0}`);
  }
  const dataset = await page.request.post(`${api}/dataset/confirm`, { data: {
    session_id: sessionId, csv_text: `${rows.join("\n")}\n`, target: "target", task: "binary_classification", id_columns: [],
  } });
  expect(dataset.ok()).toBeTruthy();
  const fis = await page.request.post(`${api}/fis/default`, { data: { session_id: sessionId, name: "Manual comparison FIS", input_columns: ["temperature"] } });
  expect(fis.ok()).toBeTruthy();
  const trained = await page.request.post(`${api}/training/run`, { data: {
    session_id: sessionId, model_kind: "logistic_regression", seed: 37, max_epochs: 1, learning_rate: 0.01,
    batch_size: 16, patience: 1, validation_fraction: 0.2, test_fraction: 0.2, max_rules: 3,
  } });
  expect(trained.ok()).toBeTruthy();
  const runId = (await trained.json()).run_id as string;
  let fisReads = 0;
  await page.route("**/fis/active", async (route) => {
    fisReads += 1;
    if (fisReads === 1) await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary FIS read failure" }) });
    else await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByTestId("comparison-model-context-error")).toContainText("Temporary FIS read failure");
  await expect(page.locator("label.comparison-choice").filter({ hasText: "Manual mamdani FIS" })).toHaveCount(0);
  await page.getByRole("button", { name: "Retry saved model context" }).click();
  const manualChoice = page.locator("label.comparison-choice").filter({ hasText: "Manual mamdani FIS" }).locator("input");
  const runChoice = page.locator("label.comparison-choice").filter({ hasText: runId.slice(0, 12) }).locator("input");
  await expect(manualChoice).toBeVisible();
  await expect(runChoice).toBeVisible();
  expect(fisReads).toBe(2);
  await manualChoice.check();
  await runChoice.check();
  await page.getByRole("button", { name: "Compare 2 selected models" }).click();
  await expect(page.getByText("SAVED MODEL COMPARISON · VALIDATION ONLY", { exact: true })).toBeVisible();
  const response = await page.request.get(`${api}/${sessionId}/analyses/comparisons/latest`);
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toMatchObject({ run_ids: [runId], fis_id: (await fis.json()).fis_id, validation_alignment: "same_cases" });

  await page.getByLabel("Slice name").fill("Temperature validation slice");
  await page.getByLabel("Slice minimum").fill("20");
  await page.getByRole("button", { name: "Run and persist slice" }).click();
  await expect(page.getByRole("cell", { name: "Temperature validation slice" })).toBeVisible();
  const sliceResponse = await page.request.get(`${api}/${sessionId}/analyses/slices/latest`);
  expect(sliceResponse.ok()).toBeTruthy();
  expect((await sliceResponse.json()).definitions[0].name).toBe("Temperature validation slice");

  let sliceWrites = 0;
  await page.route("**/api/projects/analyses/slices", async (route) => {
    sliceWrites += 1;
    await route.continue();
  });
  await page.getByLabel("Slice type").selectOption("manual");
  await page.getByLabel("Slice name").fill("Exact source-row slice");
  await page.getByLabel("Slice source rows").fill("2,invalid");
  await page.getByRole("button", { name: "Run and persist slice" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "source row IDs" })).toBeVisible();
  expect(sliceWrites).toBe(0);
  await page.getByLabel("Slice source rows").fill("2, 7");
  await page.getByRole("button", { name: "Run and persist slice" }).click();
  await expect(page.getByRole("cell", { name: "Exact source-row slice" })).toBeVisible();
  expect(sliceWrites).toBe(1);
  const manualSliceResponse = await page.request.get(`${api}/${sessionId}/analyses/slices/latest`);
  expect(manualSliceResponse.ok()).toBeTruthy();
  expect((await manualSliceResponse.json()).definitions[0].source_rows).toEqual([2, 7]);

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("SAVED MODEL COMPARISON · VALIDATION ONLY", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Exact source-row slice" })).toBeVisible();
});
