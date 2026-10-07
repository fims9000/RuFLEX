import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const evidenceScreenshot = resolve(import.meta.dirname, "../../docs/product/screenshots/20_stability_lab.png");
const updateProductEvidence = process.env.RUFLEX_UPDATE_STABILITY_EVIDENCE === "1";

function path(): string { return join(tmpdir(), `ruflex-stability-${Date.now()}-${Math.random().toString(16).slice(2)}`); }
function csv(): string { const rows = ["temperature,torque,target"]; for (let i = 0; i < 72; i += 1) { const temperature = 20 + i * .8; const torque = 10 + (i * 7) % 50; rows.push(`${temperature},${torque},${temperature + torque > 58 ? 1 : 0}`); } return `${rows.join("\n")}\n`; }

test("Stability Lab persists fixed-split multi-run evidence and its validation-only gate", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  const root = path();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Project path").fill(root); await page.getByLabel("Project name").fill("Stability Lab"); await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click(); await page.getByLabel("CSV data").fill(csv()); await page.getByRole("button", { name: "Inspect dataset", exact: true }).click(); await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("random_forest"); await page.getByLabel("Study randomness protocol").selectOption("TRAINING_VARIABILITY"); await page.getByLabel("Study split seed").fill("42"); await page.getByLabel("Study seeds").fill("11, 13, 17");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Training variability fixes split membership/)).toBeVisible();
  let evaluationCreateCount = 0;
  await page.route("**/api/projects/analyses/evaluations", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    evaluationCreateCount += 1;
    await route.fetch();
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Stability Evaluation response lost after persistence" }) });
  });
  await page.getByRole("button", { name: "Create Study Stability Analysis", exact: true }).click();
  await expect(page.getByTestId("stability-analysis-recovery")).toContainText("Stability Evaluation response lost after persistence");
  await page.getByRole("button", { name: "Retry saved chain lookup", exact: true }).click();
  await expect(page.getByTestId("stability-analysis-recovery")).toContainText("no threshold is visible yet");
  await page.getByRole("button", { name: "Continue this chain explicitly", exact: true }).click();
  await expect(page.getByText("Case Stability Map · selected-run agreement; red = high-confidence unstable", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("stability-analysis-recovery")).toHaveCount(0);
  expect(evaluationCreateCount).toBe(1);
  let stabilityGateCreateCount = 0;
  await page.route("**/api/projects/analyses/stability-policies", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    stabilityGateCreateCount += 1;
    await route.fetch();
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Stability Gate response lost after persistence" }) });
  });
  await page.getByRole("button", { name: "Freeze Stability Gate", exact: true }).click();
  await expect(page.getByTestId("stability-gate-recovery")).toContainText("Stability Gate response lost after persistence");
  await page.getByRole("button", { name: "Retry saved gate lookup", exact: true }).click();
  await expect(page.getByText("Risk–coverage comparison (same coverage)", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("stability-gate-recovery")).toHaveCount(0);
  expect(stabilityGateCreateCount).toBe(1);
  await page.getByLabel("Collapse explorer").click();
  await page.getByLabel("Collapse properties").click();
  await page.getByLabel("Collapse jobs panel").click();
  await page.getByText("Case Stability Map · selected-run agreement; red = high-confidence unstable", { exact: true }).scrollIntoViewIfNeeded();
  await page.locator(".workspace").evaluate((workspace) => { workspace.scrollLeft = 0; });
  const screenshotPath = updateProductEvidence ? evidenceScreenshot : testInfo.outputPath("20_stability_lab.png");
  await mkdir(resolve(screenshotPath, ".."), { recursive: true });
  await page.screenshot({ path: screenshotPath });
  let stabilityListFailures = 2;
  let stabilityListRequests = 0;
  await page.route(/\/api\/projects\/[^/]+\/analyses\/stability$/, async (route) => {
    stabilityListRequests += 1;
    if (stabilityListFailures > 0) {
      stabilityListFailures -= 1;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary StabilityAnalysis read failure" }) });
      return;
    }
    await route.continue();
  });
  let gateListFailures = 2;
  await page.route(/\/api\/projects\/[^/]+\/analyses\/stability-policies$/, async (route) => {
    if (gateListFailures > 0) {
      gateListFailures -= 1;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary StabilityGatePolicy read failure" }) });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Close", exact: true }).click(); await page.getByLabel("Project path").fill(root); await page.getByRole("button", { name: "Open project", exact: true }).click(); await page.getByRole("button", { name: "S", exact: true }).click();
  expect(stabilityListRequests).toBeGreaterThan(0);
  await expect(page.getByTestId("stability-analysis-load-error")).toContainText("Temporary StabilityAnalysis read failure");
  await expect(page.getByTestId("stability-policy-load-error")).toContainText("Temporary StabilityGatePolicy read failure");
  await expect(page.getByRole("button", { name: "Create Study Stability Analysis", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry Stability Analysis", exact: true }).click();
  await expect(page.getByText("Case Stability Map · selected-run agreement; red = high-confidence unstable", { exact: true })).toBeVisible();
  await expect(page.getByTestId("stability-analysis-load-error")).toHaveCount(0);
  await expect(page.getByTestId("stability-policy-load-error")).toHaveCount(0);
  await page.getByRole("button", { name: "P", exact: true }).click();
  const frozenPolicyNode = page.locator(".lineage-stability_gate_policy").first();
  await expect(frozenPolicyNode).toBeVisible();
  await frozenPolicyNode.click({ force: true });
  await expect(page.getByText("Opened lineage object: Stability-aware review", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("The saved Stability Gate is bound to a different run, Evaluation, threshold or dataset and will not be applied here.", { exact: true })).toBeVisible();
});
