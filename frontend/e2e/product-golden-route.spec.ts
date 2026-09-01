import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-product-route-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

test("PRODUCT-01 persists data, builds an editable FIS, runs it and exposes exact trace", async ({ page }) => {
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Golden route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();

  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText("Stored dataset preview", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "80", exact: true })).toBeVisible();

  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await expect(page.getByText("CANONICAL FUZZY DESIGNER", { exact: true })).toBeVisible();
  await expect(page.getByText(/mamdani · executable model/)).toBeVisible();
  await page.getByLabel("Low family").selectOption("gaussian");
  await page.getByLabel("temperature Low p2").press("ArrowLeft");
  const handle = page.getByLabel("Low parameter 1");
  await handle.focus();
  await handle.press("ArrowRight");
  await page.getByLabel("Rule 1 weight").fill("0.8");
  await page.getByLabel("FIS family").selectOption("sugeno");
  await page.getByLabel("Rule 1 Sugeno value").fill("0.8");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByText(/Canonical executable FIS saved with a semantic hash/)).toBeVisible();

  await page.getByRole("button", { name: "Run exact inference", exact: true }).click();
  await expect(page.getByText("OUTPUT", { exact: true })).toBeVisible();
  await expect(page.getByText(/trace error/)).toBeVisible();
  await page.getByRole("button", { name: "Open exact trace", exact: true }).click();
  await expect(page.getByText("E4 · EXACT COMPUTATIONAL TRACE", { exact: true })).toBeVisible();
  await expect(page.getByText(/This view reports the actual fuzzy computation/)).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /target.*3 rows/ }).click();
  await expect(page.getByText("Stored dataset preview", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Risk FIS.*sugeno/ }).click();
  await expect(page.getByText("CANONICAL FUZZY DESIGNER", { exact: true })).toBeVisible();
  await expect(page.getByLabel("FIS family")).toHaveValue("sugeno");
});
