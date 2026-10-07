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
  await page.getByRole("button", { name: "Retry exact MATLAB FIS import", exact: true }).evaluate((button) => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
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

test("MATLAB FIS import disables duplicate submissions while the import is in flight", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-fis-import-guard-${Date.now()}`);
  let importRequests = 0;
  await page.route("**/api/projects/fis/import/matlab", async (route) => {
    importRequests += 1;
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.continue();
  });
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("FIS import guard");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "M", exact: true }).click();
  await page.getByLabel("MATLAB FIS file").setInputFiles({ name: "tipper.fis", mimeType: "text/plain", buffer: Buffer.from(matlabFis) });
  await expect(page.getByRole("button", { name: "Importing MATLAB FIS…", exact: true })).toBeDisabled();
  expect(importRequests).toBe(1);
  await expect(page.getByRole("heading", { name: "tipper", exact: true })).toBeVisible();
  expect(importRequests).toBe(1);
});

test("MATLAB FIS import completion does not overwrite an editor draft created while it is pending", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-fis-import-draft-${Date.now()}`);
  let importRequests = 0;
  let secondImportedResolution: number | undefined;
  let savedDraftResolution: number | undefined;
  await page.route("**/api/projects/fis/save", async (route) => {
    if (route.request().method() === "POST") {
      savedDraftResolution = route.request().postDataJSON().spec.operators.centroid_resolution;
    }
    return route.continue();
  });
  let releaseImport: () => void = () => {};
  let importStarted: () => void = () => {};
  const importStartedPromise = new Promise<void>((resolve) => { importStarted = resolve; });
  await page.route("**/api/projects/fis/import/matlab", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    importRequests += 1;
    if (importRequests === 1) return route.continue();
    const response = await route.fetch();
    const payload = await response.json() as { spec?: { operators?: { centroid_resolution?: number } } };
    secondImportedResolution = payload.spec?.operators?.centroid_resolution;
    importStarted();
    await new Promise<void>((resolve) => { releaseImport = resolve; });
    await route.fulfill({ status: response.status(), contentType: "application/json", body: JSON.stringify(payload) });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("FIS import draft preservation");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "M", exact: true }).click();
  await page.getByLabel("MATLAB FIS file").setInputFiles({ name: "tipper.fis", mimeType: "text/plain", buffer: Buffer.from(matlabFis) });
  await expect(page.getByRole("heading", { name: "tipper", exact: true })).toBeVisible();

  const resolution = page.getByLabel("Resolution", { exact: true });
  const draftResolution = Number(await resolution.inputValue()) + 7;
  const secondImportedFis = matlabFis.replace("Name='tipper'", "Name='tipper_v2'");
  await page.getByLabel("MATLAB FIS file").setInputFiles({ name: "tipper_v2.fis", mimeType: "text/plain", buffer: Buffer.from(secondImportedFis) });
  await importStartedPromise;
  await resolution.fill(String(draftResolution));
  await resolution.blur();
  await expect(resolution).toHaveValue(String(draftResolution));
  expect(secondImportedResolution).toBeDefined();
  expect(secondImportedResolution).not.toBe(draftResolution);
  releaseImport();

  await expect(resolution).toHaveValue(String(draftResolution));
  await expect(page.getByText(/newer editor changes remain unsaved\. Save again to activate your draft/)).toBeVisible();
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedDraftResolution).toBe(draftResolution);
  expect(importRequests).toBe(2);
});
