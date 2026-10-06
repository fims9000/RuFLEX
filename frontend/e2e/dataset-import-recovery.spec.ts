import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("a persisted file import is reconciled after its confirmation read fails", async ({ page }) => {
  let datasetReads = 0;
  await page.route("**/api/projects/*/dataset", async (route) => {
    datasetReads += 1;
    if (datasetReads === 2) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "confirmation read temporarily unavailable" }) });
      return;
    }
    await route.continue();
  });

  const projectPath = join(tmpdir(), `ruflex-dataset-import-recovery-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Dataset import recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "recovery.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("sensor,target\na,0\nb,1\nc,0\nd,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toBeVisible();
  await page.getByLabel("Target").selectOption("target");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();

  const error = page.getByRole("alert").filter({ hasText: "Could not verify persisted dataset state" });
  await expect(error).toContainText("confirmation read temporarily unavailable");
  await expect(page.getByText(/Selected: recovery\.csv/)).toBeVisible();
  await error.getByRole("button", { name: "Retry dataset check", exact: true }).click();

  await expect(page.getByText(/Contract: target/)).toBeVisible();
  await expect(page.getByText(/Selected: recovery\.csv/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirm target and import file", exact: true })).toHaveCount(0);
  expect(datasetReads).toBe(3);
});
