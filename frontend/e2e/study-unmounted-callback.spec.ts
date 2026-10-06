import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-study-unmounted-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
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

test("a completed Study response from a closed project cannot hydrate the next project", async ({ page }) => {
  test.setTimeout(60_000);
  const sourcePath = projectPath("source");
  const nextPath = projectPath("next");
  const nextCreated = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path: nextPath, name: "Next study-free project" } });
  expect(nextCreated.status()).toBe(201);

  let releaseStudy!: () => void;
  let markStudyPersisted!: () => void;
  const studyGate = new Promise<void>((resolve) => { releaseStudy = resolve; });
  const studyPersisted = new Promise<void>((resolve) => { markStudyPersisted = resolve; });
  let persistedStudyId = "";
  let selectedRunId = "";
  let studyStarted = false;
  await page.route("**/api/projects/training/study-jobs", async (route) => {
    if (route.request().method() === "POST") studyStarted = true;
    await route.continue();
  });
  await page.route("**/api/projects/*/training/studies/latest", async (route) => {
    if (!studyStarted) return route.continue();
    const response = await route.fetch();
    if (!response.ok()) return route.fulfill({ response });
    const payload = await response.json() as { study_id: string; seed_runs: Array<{ run_id: string }>; selected_run_id: string };
    persistedStudyId = payload.study_id;
    selectedRunId = payload.selected_run_id;
    markStudyPersisted();
    await studyGate;
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(sourcePath);
  await page.getByLabel("Project name").fill("Study source project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByLabel("Study seeds").fill("3101, 3102, 3103");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  await studyPersisted;

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(nextPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Next study-free project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "S", exact: true }).click();

  try {
    const studyResponse = page.waitForResponse((response) =>
      response.url().endsWith("/training/studies/latest") && response.request().method() === "GET",
    );
    releaseStudy();
    await studyResponse;
    await expect(page.locator(".project-object-tree")).toContainText("No studies yet");
    expect(persistedStudyId).toBeTruthy();
    expect(selectedRunId).toBeTruthy();
    await expect(page.locator(".project-object-tree")).not.toContainText(persistedStudyId.slice(0, 8));
    await expect(page.locator(".project-object-tree")).not.toContainText(selectedRunId.slice(0, 8));
  } finally {
    releaseStudy();
  }
});
