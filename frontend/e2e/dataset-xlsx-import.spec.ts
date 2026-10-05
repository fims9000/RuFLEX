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
  page.on("request", (request) => {
    if (request.url().endsWith("/api/projects/dataset/import")) importRequests += 1;
  });
  await page.getByLabel("Target").fill("target");
  const validImport = page.waitForResponse((response) => response.url().endsWith("/api/projects/dataset/import") && response.request().method() === "POST");
  const validUpload = {
    name: "measurements.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: tinyWorkbook(),
  };
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles(validUpload);
  await expect(page.getByText("Selected: measurements.xlsx · target: target", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm target and import file", exact: true })).toBeEnabled();
  expect(importRequests).toBe(0);
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();
  const validResponse = await validImport;
  expect(validResponse.status()).toBe(200);
  const imported = await validResponse.json();
  expect(imported.contract.target).toBe("target");
  expect(imported.contract.source_format).toBe("xlsx");
  expect(imported.contract.source_artifact_sha256).toMatch(/^[a-f0-9]{64}$/);
  const frozenContract = imported.contract;
  await expect(page.getByText(new RegExp(`Source: XLSX · SHA-256: ${frozenContract.source_artifact_sha256}`))).toBeVisible();

  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "broken.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from("temperature,target\n99,0\n"),
  });
  const rejectedImport = page.waitForResponse((response) => response.url().endsWith("/api/projects/dataset/import") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Confirm target and import file", exact: true }).click();
  const invalidResponse = await rejectedImport;
  expect(invalidResponse.status()).toBe(422);
  await expect(page.getByRole("alert")).toContainText("extension/content mismatch");

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
