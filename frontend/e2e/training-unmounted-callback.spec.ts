import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-training-unmounted-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
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

test("a persisted TrainingRun response from a closed project cannot hydrate the next project", async ({ page }) => {
  test.setTimeout(35_000);
  const sourcePath = projectPath("source");
  const nextPath = projectPath("next");
  const nextCreated = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path: nextPath, name: "Next run-free project" } });
  expect(nextCreated.status()).toBe(201);

  let releaseTraining!: () => void;
  let markTrainingPersisted!: () => void;
  const trainingGate = new Promise<void>((resolve) => { releaseTraining = resolve; });
  const trainingPersisted = new Promise<void>((resolve) => { markTrainingPersisted = resolve; });
  let persistedRunId = "";
  await page.route("**/api/projects/training/run", async (route) => {
    const response = await route.fetch();
    const payload = await response.json() as { run_id: string };
    persistedRunId = payload.run_id;
    markTrainingPersisted();
    await trainingGate;
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(sourcePath);
  await page.getByLabel("Project name").fill("Training source project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await trainingPersisted;

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(nextPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Next run-free project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "S", exact: true }).click();

  try {
    const trainingResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/training/run") && response.request().method() === "POST",
    );
    releaseTraining();
    await trainingResponse;
    await expect(page.locator(".project-object-tree")).toContainText("No studies yet");
    await expect(page.locator(".project-object-tree")).not.toContainText(persistedRunId.slice(0, 8));
    await expect(page.locator(".project-object-tree")).not.toContainText("Decision Tree");
  } finally {
    releaseTraining();
  }
});

test("a TrainingRun response after workbench navigation still updates its active project", async ({ page }) => {
  test.setTimeout(30_000);
  const path = projectPath("same-project-navigation");
  let releaseTraining!: () => void;
  let markTrainingPersisted!: () => void;
  const trainingGate = new Promise<void>((resolve) => { releaseTraining = resolve; });
  const trainingPersisted = new Promise<void>((resolve) => { markTrainingPersisted = resolve; });
  let persistedRunId = "";
  await page.route("**/api/projects/training/run", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    const payload = await response.json() as { run_id: string };
    persistedRunId = payload.run_id;
    markTrainingPersisted();
    await trainingGate;
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Same-session navigation project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await trainingPersisted;

  await page.getByRole("button", { name: "P", exact: true }).click();
  try {
    const trainingResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/training/run") && response.request().method() === "POST",
    );
    releaseTraining();
    await trainingResponse;
    expect(persistedRunId).toBeTruthy();
    await expect(page.locator(".project-object-tree")).toContainText("Decision Tree");
    await expect(page.locator(".project-object-tree")).toContainText(persistedRunId.slice(0, 8));
  } finally {
    releaseTraining();
  }
});
