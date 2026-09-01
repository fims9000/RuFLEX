import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-train-evaluate-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function trainingCsv(): string {
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 36; index += 1) {
    const temperature = 10 + index * 0.7;
    const torque = 20 + (index * 11) % 60;
    const target = temperature + torque > 60 ? 1 : 0;
    rows.push(`${temperature.toFixed(2)},${torque.toFixed(2)},${target}`);
  }
  return `${rows.join("\n")}\n`;
}

test("PRODUCT-02 performs real neuro-fuzzy training, validation evaluation and reopen", async ({ page }) => {
  test.setTimeout(45_000);
  const path = projectPath();

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Training route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();

  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 36/)).toBeVisible();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText("Stored dataset preview", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.getByText("REAL TRAINING ENGINE", { exact: true })).toBeVisible();
  await page.getByLabel("Epochs").fill("2");
  await page.getByLabel("Batch size").fill("16");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();

  const runEvidence = page.locator(".run-provenance");
  await expect(runEvidence).toBeVisible({ timeout: 30_000 });
  await expect(runEvidence).toContainText("model artifact persisted");
  await expect(page.locator(".run-summary-strip")).toBeVisible();
  await expect(page.getByText("Training trajectory · epoch 0 included", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("VALIDATION EVIDENCE", { exact: true })).toBeVisible();
  const evaluationFooter = page.locator(".evaluation-footer");
  await expect(evaluationFooter).toBeVisible();
  await expect(evaluationFooter).toContainText("test rows remain locked");
  await expect(page.getByRole("heading", { name: "Validation prediction evidence", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Training run/ }).click();
  await expect(page.locator(".run-provenance")).toBeVisible();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted");
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("VALIDATION EVIDENCE", { exact: true })).toBeVisible();
});
