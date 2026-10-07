import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("edits made during a save remain as an unsaved draft", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-save-race-${Date.now()}`);
  const savedSpecs: Array<{ operators: { centroid_resolution: number } }> = [];
  let revisionRequests = 0;
  let releaseFirstSave: () => void = () => {};
  let firstSaveStarted: () => void = () => {};
  const firstSaveStartedPromise = new Promise<void>((resolve) => { firstSaveStarted = resolve; });
  await page.route("**/fis/revisions", async (route) => {
    revisionRequests += 1;
    if (revisionRequests === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporary revision-history failure" }) });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/projects/fis/save", async (route) => {
    savedSpecs.push(route.request().postDataJSON().spec as { operators: { centroid_resolution: number } });
    if (savedSpecs.length === 1) {
      firstSaveStarted();
      await new Promise<void>((resolve) => { releaseFirstSave = resolve; });
    }
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS save race");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  await expect(page.getByTestId("fis-revision-history-error")).toBeVisible();
  const resolution = page.getByLabel("Resolution", { exact: true });
  const editBeforeRetry = Number(await resolution.inputValue()) + 1;
  await resolution.fill(String(editBeforeRetry));
  await page.getByRole("button", { name: "Retry revision history", exact: true }).click();
  await expect.poll(() => revisionRequests).toBe(2);
  await expect(resolution).toHaveValue(String(editBeforeRetry));
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await firstSaveStartedPromise;
  const editedResolution = Number(await resolution.inputValue()) + 1;
  await resolution.fill(String(editedResolution));
  await expect(resolution).toHaveValue(String(editedResolution));
  releaseFirstSave();
  await expect(page.getByText("The submitted FIS revision was saved; newer editor changes remain unsaved.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedSpecs.length).toBe(2);
  await expect(page.getByText("Canonical executable FIS saved with a semantic hash.", { exact: true })).toBeVisible();
  expect(savedSpecs[1].operators.centroid_resolution).toBe(editedResolution);
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeEnabled();
});

test("an undo made during save remains selected when the persisted result hydrates", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-undo-save-race-${Date.now()}`);
  let releaseSave: () => void = () => {};
  let saveStarted: () => void = () => {};
  const saveStartedPromise = new Promise<void>((resolve) => { saveStarted = resolve; });
  let savePosts = 0;
  await page.route("**/api/projects/fis/save", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    savePosts += 1;
    const response = await route.fetch();
    if (savePosts === 1) {
      saveStarted();
      await new Promise<void>((resolve) => { releaseSave = resolve; });
    }
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS undo save race");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  const resolution = page.getByLabel("Resolution", { exact: true });
  const baseResolution = Number(await resolution.inputValue());
  await resolution.fill(String(baseResolution + 3));
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await saveStartedPromise;

  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(resolution).toHaveValue(String(baseResolution));
  releaseSave();

  await expect(page.getByText(/newer editor changes remain unsaved/)).toBeVisible();
  await expect(resolution).toHaveValue(String(baseResolution));
  await expect(page.getByRole("button", { name: "Redo", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(resolution).toHaveValue(String(baseResolution + 3));
  expect(savePosts).toBe(1);
});

test("exact retry after an uncertain FIS save preserves edits made while the retry is in flight", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-retry-race-${Date.now()}`);
  const savedSpecs: Array<{ operators: { centroid_resolution: number } }> = [];
  let releaseRetry: () => void = () => {};
  let retryStarted: () => void = () => {};
  const retryStartedPromise = new Promise<void>((resolve) => { retryStarted = resolve; });
  await page.route("**/api/projects/fis/save", async (route) => {
    const saveNumber = savedSpecs.length + 1;
    savedSpecs.push(route.request().postDataJSON().spec as { operators: { centroid_resolution: number } });
    if (saveNumber === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "FIS save did not reach persistence" }) });
      return;
    }
    const response = await route.fetch();
    if (saveNumber === 2) {
      retryStarted();
      await new Promise<void>((resolve) => { releaseRetry = resolve; });
    }
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS exact retry draft preservation");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  const resolution = page.getByLabel("Resolution", { exact: true });
  const pendingResolution = Number(await resolution.inputValue()) + 1;
  await resolution.fill(String(pendingResolution));
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByTestId("fis-save-recovery")).toContainText("FIS save did not reach persistence");
  await page.getByRole("button", { name: "Retry exact FIS revision lookup", exact: true }).click();
  await expect(page.getByRole("button", { name: "Explicitly repeat unchanged FIS save", exact: true })).toBeEnabled();

  const repeat = page.getByRole("button", { name: "Explicitly repeat unchanged FIS save", exact: true });
  await repeat.evaluate((button) => { button.dispatchEvent(new MouseEvent("click", { bubbles: true })); button.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await retryStartedPromise;
  expect(savedSpecs).toHaveLength(2);
  expect(savedSpecs[1].operators.centroid_resolution).toBe(pendingResolution);
  const newerResolution = pendingResolution + 1;
  await resolution.fill(String(newerResolution));
  releaseRetry();
  await expect(page.getByText(/The exact FIS snapshot was safely repeated; newer editor changes remain unsaved/)).toBeVisible();
  await expect(resolution).toHaveValue(String(newerResolution));
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedSpecs).toHaveLength(3);
  expect(savedSpecs[2].operators.centroid_resolution).toBe(newerResolution);
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeEnabled();
});

test("dataset range response cannot overwrite an FIS draft edited while it is pending", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-range-race-${Date.now()}`);
  let releaseRange: () => void = () => {};
  let rangeStarted: () => void = () => {};
  const rangeStartedPromise = new Promise<void>((resolve) => { rangeStarted = resolve; });
  let savedResolution: number | undefined;
  await page.route("**/api/projects/*/dataset/features/*/range", async (route) => {
    const response = await route.fetch();
    rangeStarted();
    await new Promise<void>((resolve) => { releaseRange = resolve; });
    await route.fulfill({ response });
  });
  await page.route("**/api/projects/fis/save", async (route) => {
    if (route.request().method() === "POST") savedResolution = route.request().postDataJSON().spec.operators.centroid_resolution;
    return route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS dataset range race");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  const featureMapping = page.getByLabel("Dataset feature mapping", { exact: true });
  if (!(await featureMapping.inputValue())) await featureMapping.selectOption({ index: 1 });

  await page.getByRole("button", { name: "Reset range from dataset", exact: true }).click();
  await rangeStartedPromise;
  const resolution = page.getByLabel("Resolution", { exact: true });
  const draftResolution = Number(await resolution.inputValue()) + 11;
  await resolution.fill(String(draftResolution));
  await resolution.blur();
  releaseRange();

  await expect(page.getByRole("alert")).toContainText("The FIS or feature mapping changed while the DatasetContract range was loading");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedResolution).toBe(draftResolution);
});

test("MATLAB import cannot race an in-flight FIS save", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-write-mutex-${Date.now()}`);
  let releaseSave: () => void = () => {};
  let saveStarted: () => void = () => {};
  const saveStartedPromise = new Promise<void>((resolve) => { saveStarted = resolve; });
  let importRequests = 0;
  await page.route("**/api/projects/fis/save", async (route) => {
    const response = await route.fetch();
    saveStarted();
    await new Promise<void>((resolve) => { releaseSave = resolve; });
    await route.fulfill({ response });
  });
  await page.route("**/api/projects/fis/import/matlab", async (route) => {
    importRequests += 1;
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS write mutex");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await saveStartedPromise;
  await expect(page.getByRole("button", { name: "Import MATLAB .fis", exact: true })).toBeDisabled();
  await page.getByLabel("MATLAB FIS file").setInputFiles({ name: "racing.fis", mimeType: "text/plain", buffer: Buffer.from("[System]\nName='racing'\nType='mamdani'\n") });
  await page.waitForTimeout(100);
  expect(importRequests).toBe(0);
  releaseSave();
  await expect(page.getByText("Canonical executable FIS saved with a semantic hash.", { exact: true })).toBeVisible();
  expect(importRequests).toBe(0);
});
