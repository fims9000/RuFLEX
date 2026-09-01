import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-multiseed-${Date.now()}-${Math.random().toString(16).slice(2)}`);
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

test("PRODUCT-03 persists a multi-seed Study and restores it through the project explorer", async ({ page }) => {
  test.setTimeout(60_000);
  const path = projectPath();

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Study route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Epochs").fill("1");
  await page.getByLabel("Batch size").fill("16");
  await page.getByLabel("Study seeds").fill("7, 8, 9");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/locked test was not used/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Study .*3 seed runs/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /SeedRun 7/ })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  const restoredStudy = page.getByRole("button", { name: /Study .*3 seed runs/ });
  await expect(restoredStudy).toBeVisible();
  await restoredStudy.click();
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible();
  await expect(page.getByText(/locked test was not used/)).toBeVisible();
  await expect(page.getByRole("button", { name: /SeedRun 9/ })).toBeVisible();
});
