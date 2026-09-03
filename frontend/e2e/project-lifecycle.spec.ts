import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-playwright-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

async function createProject(page: import("@playwright/test").Page, path: string, name = "Pump-01") {
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.locator(".project-identity")).toContainText(name);
}

test("E2E-01 creates a project and exposes it in Explorer and Properties", async ({ page }) => {
  await createProject(page, projectPath("create"));
  await expect(page.locator(".project-identity")).toContainText("Pump-01");
  await expect(page.locator(".project-object-tree")).toContainText("Pump-01");
  await expect(page.getByText(/^ID: [0-9a-f-]{36}$/)).toBeVisible();
});

test("E2E-02 saves metadata, closes, and reopens it", async ({ page }) => {
  const path = projectPath("reopen");
  await createProject(page, path, "Reopen");
  await page.getByLabel("Description").fill("Preserved description");
  await page.getByRole("button", { name: "Update description", exact: true }).click();
  await expect(page.getByText("Updated Reopen", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByText("Description: Preserved description", { exact: true })).toBeVisible();
  await expect(page.getByTestId("project-integrity")).toContainText("PASS");
});

test("E2E-03 read-only opening disables mutating Studio controls", async ({ page }) => {
  const path = projectPath("readonly");
  await createProject(page, path, "Read only");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Read-only").check();
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Update description", exact: true })).toBeDisabled();
});

test("E2E-04 future schema reports a controlled error", async ({ page }) => {
  const path = projectPath("future");
  await mkdir(path, { recursive: true });
  await writeFile(join(path, "project.yaml"), "schema_version: 999\n", "utf8");
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.locator(".error")).toContainText("newer than supported version");
  await expect(page.locator(".project-identity")).toHaveText("No project open");
});

test("E2E-05 backend unavailability is a controlled UI error", async ({ page }) => {
  await page.route("**/api/health", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator(".error")).toBeVisible();
  await expect(page.getByText("Create or open a RuFLEX project", { exact: true })).toBeVisible();
});

test("E2E-06 Studio starts without a Streamlit execution path", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Backend connected", { exact: true })).toBeVisible();
  await expect(page.getByText("RuFLEX Studio", { exact: true })).toBeVisible();
});

test("E2E-07 persists a content-addressed artifact and restores its Studio inventory", async ({ page }) => {
  const path = projectPath("artifact");
  await createProject(page, path, "Artifact project");
  const response = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  const opened = await response.json();
  const ingested = await page.request.post("http://127.0.0.1:8010/api/projects/artifacts/text", { data: { session_id: opened.session_id, text: "persisted studio evidence" } });
  expect(ingested.status()).toBe(201);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByText(/^[0-9a-f]{12} · 25 B · generated$/)).toBeVisible();
});

test("E2E-08 confirms a dataset contract in Data workspace and preserves it across reopen", async ({ page }) => {
  const path = projectPath("dataset");
  await createProject(page, path, "Dataset project");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 3/)).toBeVisible();
  await expect(page.getByText("Role proposals are advisory: choose target and ID columns before freezing the authoritative DatasetContract.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("ID columns")).toHaveValue("entity_id");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  await expect(page.getByText(/Row identity: dataset-fingerprint\/source-row\/v1/)).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  const reopened = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  expect(reopened.status()).toBe(200);
  const persisted = await page.request.get(`http://127.0.0.1:8010/api/projects/${(await reopened.json()).session_id}/artifacts`);
  expect(persisted.status()).toBe(200);
});

test("E2E-09 declares and freezes the new-entity generalization contract", async ({ page }) => {
  await createProject(page, projectPath("generalization"), "Generalization project");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "Declare generalization contract", exact: true }).click();
  await expect(page.getByText("Split recommendation: group · Ready to freeze", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Freeze evaluation contract", exact: true }).click();
  await expect(page.getByText("Split recommendation: group · Frozen", { exact: true })).toBeVisible();
});
