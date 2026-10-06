import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const matlabFis = `[System]
Name='tipper'
Type='mamdani'
AndMethod='min'
OrMethod='max'
ImpMethod='min'
AggMethod='max'
DefuzzMethod='centroid'

[Input1]
Name='temperature'
Range=[0 100]
MF1='low':'trimf',[0 0 50]

[Output1]
Name='risk'
Range=[0 1]
MF1='low':'trimf',[0 0 1]

[Rules]
1, 1 (1) : 1
`;

test("PRODUCT-12 preserves imported MATLAB FIS source provenance", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-fis-import-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Imported FIS");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "M", exact: true }).click();
  let revisionReads = 0;
  await page.route("**/api/projects/*/fis/revisions", async (route) => {
    revisionReads += 1;
    if (revisionReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "FIS revision history temporarily unavailable" }) });
    }
    return route.continue();
  });
  let importPostCount = 0;
  await page.route("**/api/projects/fis/import/matlab", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    importPostCount += 1;
    if (importPostCount === 1) {
      await route.fetch();
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "FIS import response lost after persistence" }) });
      return;
    }
    return route.continue();
  });
  await page.getByLabel("MATLAB FIS file").setInputFiles({ name: "tipper.fis", mimeType: "text/plain", buffer: Buffer.from(matlabFis) });
  await expect(page.getByTestId("fis-import-recovery")).toContainText("FIS import response lost after persistence");
  await page.getByRole("button", { name: "Retry exact MATLAB FIS import", exact: true }).click();
  await expect(page.getByTestId("fis-import-recovery")).toHaveCount(0);
  expect(importPostCount).toBe(2);
  await expect(page.getByText(/MATLAB FIS imported as a canonical executable model.*source artifact/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "tipper", exact: true })).toBeVisible();
  const revisionHistoryError = page.getByTestId("fis-revision-history-error");
  await expect(revisionHistoryError).toContainText("FIS revision history temporarily unavailable");
  await revisionHistoryError.getByRole("button", { name: "Retry revision history" }).click();
  await expect(revisionHistoryError).toHaveCount(0);
  expect(revisionReads).toBe(2);
  await page.getByRole("button", { name: "P", exact: true }).click();
  const fisNode = page.locator(".lineage-fis_revision").first();
  await expect(fisNode).toBeVisible();
  await expect(page.locator(".lineage-fis_revision")).toHaveCount(1);
  await fisNode.click({ force: true });
  await expect(page.getByText(/Opened lineage object: tipper · revision/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "tipper", exact: true })).toBeVisible();
});
