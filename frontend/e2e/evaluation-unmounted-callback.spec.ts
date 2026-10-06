import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-evaluation-unmounted-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function trainingCsv(): string {
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 36; index += 1) {
    const temperature = 10 + index * 0.7;
    const torque = 20 + (index * 11) % 60;
    rows.push(`${temperature.toFixed(2)},${torque.toFixed(2)},${temperature + torque > 60 ? 1 : 0}`);
  }
  return `${rows.join("\n")}\n`;
}

test("a persisted validation Evaluation response from a closed project cannot hydrate the next project", async ({ page }) => {
  test.setTimeout(35_000);
  const sourcePath = projectPath("source");
  const nextPath = projectPath("next");
  const nextCreated = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path: nextPath, name: "Next evaluation-free project" } });
  expect(nextCreated.status()).toBe(201);

  let releaseEvaluation!: () => void;
  let markEvaluationPersisted!: () => void;
  const evaluationGate = new Promise<void>((resolve) => { releaseEvaluation = resolve; });
  const evaluationPersisted = new Promise<void>((resolve) => { markEvaluationPersisted = resolve; });
  let persistedEvaluationId = "";
  await page.route("**/api/projects/analyses/evaluations", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    const payload = await response.json() as { evaluation_id: string };
    persistedEvaluationId = payload.evaluation_id;
    markEvaluationPersisted();
    await evaluationGate;
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(sourcePath);
  await page.getByLabel("Project name").fill("Evaluation source project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByTitle("ANALYSES").click();
  await page.getByRole("button", { name: "Save validation evidence", exact: true }).click();
  await evaluationPersisted;

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(nextPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Next evaluation-free project", exact: true })).toBeVisible();
  await page.getByTitle("ANALYSES").click();

  try {
    const evaluationResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/analyses/evaluations") && response.request().method() === "POST",
    );
    releaseEvaluation();
    await evaluationResponse;
    expect(persistedEvaluationId).toBeTruthy();
    await expect(page.locator(".project-object-tree")).toContainText("No analyses yet");
    await expect(page.locator(".project-object-tree")).not.toContainText(persistedEvaluationId.slice(0, 8));
    await expect(page.locator(".project-object-tree")).not.toContainText("Decision Tree");
  } finally {
    releaseEvaluation();
  }
});
