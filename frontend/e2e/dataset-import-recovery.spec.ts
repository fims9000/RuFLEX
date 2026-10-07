import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("a rejected CSV role remains correctable without a dataset-state recovery lock", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-csv-role-rejection-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Correctable CSV roles");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Role for entity_id" })).toBeVisible();
  await page.getByRole("textbox", { name: "ID columns" }).fill("missing_id");
  await expect(page.getByRole("textbox", { name: "ID columns" })).toHaveValue("missing_id");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await expect(page.getByRole("alert")).toContainText("ID columns are absent from the dataset");
  await expect(page.getByText("Could not verify persisted dataset state.")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeEnabled();
  await page.getByRole("textbox", { name: "ID columns" }).fill("");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
});

test("a rejected file role remains correctable without reselecting the file", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-file-role-rejection-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Correctable file roles");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "roles.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("sensor,target\n10,0\n20,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toContainText("roles.csv");
  await page.getByLabel("Target", { exact: true }).selectOption("target");
  await page.getByRole("textbox", { name: "Exclude from model" }).fill("missing_feature");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();

  await expect(page.getByRole("alert").filter({ hasText: "Excluded columns are absent" })).toBeVisible();
  await expect(page.getByText("Could not verify persisted dataset state.")).toHaveCount(0);
  await expect(page.getByLabel("Selected file schema preview")).toContainText("roles.csv");
  await page.getByRole("textbox", { name: "Exclude from model" }).fill("");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
});

test("a rejected replacement import preserves the previously saved DatasetContract", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-replacement-role-rejection-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Replacement role recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "first.csv", mimeType: "text/csv", buffer: Buffer.from("sensor,target\n10,0\n20,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toContainText("first.csv");
  await page.getByLabel("Target", { exact: true }).selectOption("target");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  const originalSha = await page.locator(".data-summary code").first().textContent();

  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "second.csv", mimeType: "text/csv", buffer: Buffer.from("sensor,target\n30,0\n40,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toContainText("second.csv");
  await page.getByLabel("Target", { exact: true }).selectOption("target");
  await page.getByRole("textbox", { name: "Exclude from model" }).fill("missing_feature");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();

  await expect(page.getByRole("alert").filter({ hasText: "Excluded columns are absent" })).toBeVisible();
  await expect(page.getByLabel("Selected file schema preview")).toContainText("second.csv");
  await expect(page.locator(".data-summary code").first()).toHaveText(originalSha ?? "");
  await page.getByRole("textbox", { name: "Exclude from model" }).fill("");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();
  await expect(page.locator(".data-summary code").first()).not.toHaveText(originalSha ?? "");
});

test("a rejected replacement CSV retains its draft beside the frozen prior contract", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-replacement-csv-rejection-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Replacement CSV recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Role for entity_id" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  const originalSha = await page.locator(".data-summary code").first().textContent();

  await page.getByLabel("CSV data").fill("sensor,target\n30,0\n40,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Role for sensor" })).toBeVisible();
  await page.getByRole("textbox", { name: "ID columns" }).fill("missing_id");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await expect(page.getByRole("alert").filter({ hasText: "ID columns are absent" })).toBeVisible();
  await expect(page.locator(".data-summary code").first()).toHaveText(originalSha ?? "");
  await expect(page.getByRole("combobox", { name: "Role for sensor" })).toBeVisible();
  await page.getByRole("textbox", { name: "ID columns" }).fill("");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.locator(".data-summary code").first()).not.toHaveText(originalSha ?? "");
});

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
  await page.getByLabel("Target", { exact: true }).selectOption("target");
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

test("a committed file import is not repeated when its HTTP response is lost", async ({ page }) => {
  let importRequests = 0;
  await page.route("**/api/projects/dataset/import", async (route) => {
    importRequests += 1;
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    await route.abort("connectionreset");
  });

  const projectPath = join(tmpdir(), `ruflex-dataset-import-lost-response-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Lost import response");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "committed.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("sensor,target\na,0\nb,1\nc,0\nd,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toBeVisible();
  await page.getByLabel("Target", { exact: true }).selectOption("target");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();

  await expect(page.getByText(/restored its confirmation after the upload response was lost/)).toBeVisible();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  await expect(page.getByText(/Selected: committed\.csv/)).toHaveCount(0);
  expect(importRequests).toBe(1);
});

test("a lost import response and failed recovery read reconcile on the next dataset retry", async ({ page }) => {
  let importRequests = 0;
  let datasetReads = 0;
  let importCommitted = false;
  let failedRecoveryRead = false;
  await page.route("**/api/projects/*/dataset", async (route) => {
    datasetReads += 1;
    if (importCommitted && !failedRecoveryRead) {
      failedRecoveryRead = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "recovery read temporarily unavailable" }) });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/projects/dataset/import", async (route) => {
    importRequests += 1;
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    importCommitted = true;
    await route.abort("connectionreset");
  });

  const projectPath = join(tmpdir(), `ruflex-dataset-import-double-recovery-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Double recovery import");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "double-recovery.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("sensor,target\na,0\nb,1\nc,0\nd,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toBeVisible();
  await page.getByLabel("Target", { exact: true }).selectOption("target");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();

  const error = page.getByRole("alert").filter({ hasText: "Could not verify persisted dataset state" });
  await expect(error).toBeVisible();
  expect(failedRecoveryRead).toBe(true);
  await expect(page.getByText(/Selected: double-recovery\.csv/)).toBeVisible();
  await error.getByRole("button", { name: "Retry dataset check", exact: true }).click();

  await expect(page.getByText(/Contract: target/)).toBeVisible();
  await expect(page.getByText(/Selected: double-recovery\.csv/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirm target and import file", exact: true })).toHaveCount(0);
  expect(importRequests).toBe(1);
  expect(datasetReads).toBeGreaterThanOrEqual(2);
});

test("a saved editable CSV contract is restored when its response is lost", async ({ page }) => {
  let confirmationRequests = 0;
  await page.route("**/api/projects/dataset/confirm", async (route) => {
    confirmationRequests += 1;
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    await route.abort("connectionreset");
  });

  const projectPath = join(tmpdir(), `ruflex-csv-confirm-lost-response-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("CSV confirmation recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await expect(page.getByText(/restored confirmation after the response was lost/)).toBeVisible();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  expect(confirmationRequests).toBe(1);
});

test("a lost CSV confirmation and failed recovery read reconcile on the next dataset retry", async ({ page }) => {
  let confirmationRequests = 0;
  let confirmationCommitted = false;
  let failedRecoveryRead = false;
  await page.route("**/api/projects/*/dataset", async (route) => {
    if (confirmationCommitted && !failedRecoveryRead) {
      failedRecoveryRead = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "CSV recovery read temporarily unavailable" }) });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/projects/dataset/confirm", async (route) => {
    confirmationRequests += 1;
    const response = await route.fetch();
    expect(response.ok()).toBeTruthy();
    confirmationCommitted = true;
    await route.abort("connectionreset");
  });

  const projectPath = join(tmpdir(), `ruflex-csv-double-recovery-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("CSV double recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  const error = page.getByRole("alert").filter({ hasText: "Could not verify persisted dataset state" });
  await expect(error).toBeVisible();
  expect(failedRecoveryRead).toBe(true);
  await error.getByRole("button", { name: "Retry dataset check", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  await expect(page.getByText(/saved CSV DatasetContract matches the pending request/)).toBeVisible();
  expect(confirmationRequests).toBe(1);
});
