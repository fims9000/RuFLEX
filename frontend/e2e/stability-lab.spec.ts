import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function path(): string { return join(tmpdir(), `ruflex-stability-${Date.now()}-${Math.random().toString(16).slice(2)}`); }
function csv(): string { const rows = ["temperature,torque,target"]; for (let i = 0; i < 72; i += 1) { const temperature = 20 + i * .8; const torque = 10 + (i * 7) % 50; rows.push(`${temperature},${torque},${temperature + torque > 58 ? 1 : 0}`); } return `${rows.join("\n")}\n`; }

test("Stability Lab persists fixed-split multi-run evidence and its validation-only gate", async ({ page }) => {
  test.setTimeout(90_000);
  const root = path();
  await page.goto("/");
  await page.getByLabel("Project path").fill(root); await page.getByLabel("Project name").fill("Stability Lab"); await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click(); await page.getByLabel("CSV data").fill(csv()); await page.getByRole("button", { name: "Inspect dataset", exact: true }).click(); await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("random_forest"); await page.getByLabel("Study randomness protocol").selectOption("TRAINING_VARIABILITY"); await page.getByLabel("Study split seed").fill("42"); await page.getByLabel("Study seeds").fill("11, 13, 17");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Training variability fixes split membership/)).toBeVisible();
  await page.getByRole("button", { name: "Create Study Stability Analysis", exact: true }).click();
  await expect(page.getByText("Case Stability Map · selected-run agreement; red = high-confidence unstable", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Freeze Stability Gate", exact: true }).click();
  await expect(page.getByText("Risk–coverage comparison (same coverage)", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Close", exact: true }).click(); await page.getByLabel("Project path").fill(root); await page.getByRole("button", { name: "Open project", exact: true }).click(); await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.getByText("Case Stability Map · selected-run agreement; red = high-confidence unstable", { exact: true })).toBeVisible();
});
