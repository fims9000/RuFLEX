import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-xlsx-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function tinyWorkbook(): Buffer {
  const repoRoot = resolve(import.meta.dirname, "../..");
  const python = process.env.RUFLEX_PYTHON
    ?? (existsSync(resolve(repoRoot, ".venv/bin/python")) ? resolve(repoRoot, ".venv/bin/python") : "python3");
  const script = [
    "from io import BytesIO",
    "import base64, pandas as pd",
    "buffer = BytesIO()",
    "pd.DataFrame({'temperature': [10, 20, 30], 'target': [0, 1, 1]}).to_excel(buffer, index=False)",
    "print(base64.b64encode(buffer.getvalue()).decode())",
  ].join("; ");
  const encoded = execFileSync(python, ["-c", script], { encoding: "utf8" }).trim();
  return Buffer.from(encoded, "base64");
}

test("Studio imports XLSX with an explicit target and preserves it after rejection and reopen", async ({ page }) => {
  test.setTimeout(30_000);
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("XLSX import");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();

  let importRequests = 0;
  let inspectRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/projects/dataset/import")) importRequests += 1;
    if (request.url().endsWith("/api/projects/dataset/import/inspect")) inspectRequests += 1;
  });
  await page.getByLabel("Target").fill("target");
  const validInspection = page.waitForResponse((response) => response.url().endsWith("/api/projects/dataset/import/inspect") && response.request().method() === "POST");
  const validUpload = {
    name: "measurements.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: tinyWorkbook(),
  };
  let releaseInspection: () => void = () => {};
  const inspectionGate = new Promise<void>((resolve) => { releaseInspection = resolve; });
  await page.route("**/api/projects/dataset/import/inspect", async (route) => { await inspectionGate; await route.continue(); });
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles(validUpload);
  await expect(page.getByRole("button", { name: "Inspecting file…", exact: true })).toBeDisabled();
  releaseInspection();
  const inspectionResponse = await validInspection;
  await page.unroute("**/api/projects/dataset/import/inspect");
  expect(inspectionResponse.status()).toBe(200);
  await expect(page.getByLabel("Selected file schema preview")).toContainText("3 rows");
  await expect(page.getByLabel("Selected file schema preview")).toContainText("temperature");
  await expect(page.getByLabel("Selected file schema preview")).toContainText("target");
  await expect(page.getByText("Selected: measurements.xlsx · target: select from inspected columns", { exact: true })).toBeVisible();
  await page.getByLabel("Target").selectOption("target");
  await expect(page.getByRole("button", { name: "Confirm target and import file", exact: true })).toBeEnabled();
  expect(inspectRequests).toBe(1);
  expect(importRequests).toBe(0);
  let releaseImport: () => void = () => {};
  const importGate = new Promise<void>((resolve) => { releaseImport = resolve; });
  await page.route("**/api/projects/dataset/import", async (route) => { await importGate; await route.continue(); });
  const validImport = page.waitForResponse((response) => response.url().endsWith("/api/projects/dataset/import") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();
  await expect(page.getByRole("button", { name: "Saving file…", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Importing…", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Task")).toBeDisabled();
  releaseImport();
  const validResponse = await validImport;
  await page.unroute("**/api/projects/dataset/import");
  expect(validResponse.status()).toBe(200);
  const imported = await validResponse.json();
  expect(imported.contract.target).toBe("target");
  expect(imported.contract.source_format).toBe("xlsx");
  expect(imported.contract.source_artifact_sha256).toMatch(/^[a-f0-9]{64}$/);
  const frozenContract = imported.contract;
  await expect(page.getByText(new RegExp(`Source: XLSX · SHA-256: ${frozenContract.source_artifact_sha256}`))).toBeVisible();

  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "oversized.csv",
    mimeType: "text/csv",
    buffer: Buffer.alloc(5_000_001, 65),
  });
  await expect(page.getByRole("alert")).toContainText("exceeds the 5 MB import limit");
  await expect(page.getByText(new RegExp(`Source: XLSX · SHA-256: ${frozenContract.source_artifact_sha256}`))).toBeVisible();
  expect(inspectRequests).toBe(1);
  expect(importRequests).toBe(1);

  const rejectedInspection = page.waitForResponse((response) => response.url().endsWith("/api/projects/dataset/import/inspect") && response.request().method() === "POST");
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "broken.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from("temperature,target\n99,0\n"),
  });
  const invalidResponse = await rejectedInspection;
  expect(invalidResponse.status()).toBe(422);
  await expect(page.getByRole("alert")).toContainText("extension/content mismatch");
  await expect(page.getByRole("button", { name: "Confirm target and import file", exact: true })).toBeDisabled();
  expect(importRequests).toBe(1);

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.locator(".data-workspace")).toBeVisible();
  await expect(page.getByText(new RegExp(`Contract: target · binary_classification`))).toBeVisible();
  await expect(page.getByText(new RegExp(`Source: XLSX · SHA-256: ${frozenContract.source_artifact_sha256}`))).toBeVisible();

  const opened = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  expect(opened.status()).toBe(200);
  const reopenedState = await page.request.get(`http://127.0.0.1:8010/api/projects/${(await opened.json()).session_id}/dataset`);
  expect(reopenedState.status()).toBe(200);
  const persisted = await reopenedState.json();
  expect(persisted.contract).toEqual(frozenContract);
  expect(persisted.profile.row_count).toBe(3);
});

test("Studio invalidates a stale CSV inspection when the candidate is edited", async ({ page }) => {
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("CSV inspection refresh");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await expect(page.getByRole("status")).toContainText("editable draft only");
  await page.getByLabel("CSV data").fill("temperature,target\n10,0\n20,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeEnabled();
  await expect(page.getByText("Rows: 2 · columns: 2", { exact: false })).toBeVisible();

  await page.getByLabel("CSV data").fill("temperature,other\n30,0\n40,1\n");

  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeDisabled();
  await expect(page.getByText("CSV changed; inspect again before confirming", { exact: true })).toBeVisible();
  await expect(page.getByText("Rows: 2 · columns: 2", { exact: false })).toHaveCount(0);
});

test("Studio excludes an ordinary feature without assigning it an ID role and reopens the frozen choice", async ({ page }) => {
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Feature scope");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill("entity_id,temperature,leak_hint,target\na,10,1,0\nb,20,0,1\n");
  await page.getByLabel("ID columns").fill("entity_id");
  await page.getByRole("textbox", { name: "Exclude from model" }).fill("leak_hint");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  const roles = page.getByLabel("Frozen dataset roles");
  await expect(roles).toContainText("1 model features · 1 IDs · 1 other columns excluded");
  await roles.locator("summary").click();
  await expect(roles).toContainText("Model features: temperature");
  await expect(roles).toContainText("Excluded from model: leak_hint");

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Exclude from model" })).toHaveValue("leak_hint");
  await expect(page.getByLabel("Frozen dataset roles")).toContainText("1 model features · 1 IDs · 1 other columns excluded");
});
