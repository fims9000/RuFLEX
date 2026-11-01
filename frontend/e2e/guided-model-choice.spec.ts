import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("Studio suggests a same-case validation candidate and reopens the comparison", async ({ page }) => {
  test.setTimeout(60_000);
  const path = join(tmpdir(), `ruflex-guided-model-choice-${Date.now()}`);
  const api = "http://127.0.0.1:8010/api/projects";
  const created = await page.request.post(api, { data: { path, name: "Guided model choice" } });
  expect(created.ok()).toBeTruthy();
  const sessionId = (await created.json()).session_id as string;
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 48; index += 1) rows.push(`${10 + index},${(index * 7) % 31},${index > 22 ? 1 : 0}`);
  const dataset = await page.request.post(`${api}/dataset/confirm`, { data: {
    session_id: sessionId, csv_text: `${rows.join("\n")}\n`, target: "target", task: "binary_classification", id_columns: [],
  } });
  expect(dataset.ok()).toBeTruthy();
  const runIds: string[] = [];
  for (const model_kind of ["logistic_regression", "decision_tree"]) {
    const response = await page.request.post(`${api}/training/run`, { data: {
      session_id: sessionId, model_kind, seed: 31, split_seed: 31, training_seed: 31,
      max_epochs: 1, learning_rate: 0.01, batch_size: 16, patience: 1,
      validation_fraction: 0.2, test_fraction: 0.2, max_rules: 3,
    } });
    expect(response.status()).toBe(201);
    runIds.push((await response.json()).run_id);
  }

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  for (const runId of runIds) await page.locator("label.comparison-choice").filter({ hasText: runId.slice(0, 12) }).locator("input").check();
  await page.getByRole("button", { name: "Compare 2 selected models" }).click();
  const suggestion = page.getByTestId("validation-candidate-suggestion");
  await expect(suggestion).toContainText("Best observed candidate among 2 selected trained runs");
  const saved = await page.request.get(`${api}/${sessionId}/analyses/comparisons/latest`);
  expect(saved.ok()).toBeTruthy();
  const candidateId = (await saved.json()).candidate_suggestion.run_id as string;
  expect(runIds).toContain(candidateId);
  await suggestion.getByRole("button", { name: "Inspect suggested run" }).click();
  await expect(page.getByText(`Inspecting validation candidate`, { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByTestId("validation-candidate-suggestion")).toContainText(candidateId.slice(0, 12));
});
