import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("project evidence indexes distinguish unavailable from absent and can be retried independently", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-evidence-hydration-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  let stabilityReads = 0;
  await page.route("**/api/projects/*/analyses/stability", async (route) => {
    stabilityReads += 1;
    if (stabilityReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved stability analysis temporarily unavailable" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  let latestReads = 0;
  let artifactReads = 0;
  await page.route("**/api/projects/*/artifacts", async (route) => {
    artifactReads += 1;
    if (artifactReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "project artifact store temporarily unavailable" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/projects/*/evidence/tree-path/latest", async (route) => {
    latestReads += 1;
    if (latestReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved tree path temporarily unavailable" }) });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "no saved tree path" }) });
  });
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Evidence hydration");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByTitle("EVIDENCE").click();
  const artifactError = page.getByTestId("artifact-hydration-error");
  await expect(artifactError).toContainText("project artifact store temporarily unavailable");
  await artifactError.getByRole("button", { name: "Retry artifact list" }).click();
  await expect(artifactError).toHaveCount(0);
  await expect(page.getByText("No immutable artifacts yet.", { exact: true })).toBeVisible();
  expect(artifactReads).toBe(2);
  const hydrationError = page.getByTestId("tree-evidence-hydration-error");
  await expect(hydrationError).toContainText("saved tree path temporarily unavailable");
  await hydrationError.getByRole("button", { name: "Retry structural trace" }).click();
  await expect(hydrationError).toHaveCount(0);
  await expect(page.getByTestId("tree-evidence-empty")).toBeVisible();
  expect(latestReads).toBe(2);
  expect(stabilityReads).toBe(1);
  const stabilityError = page.locator(".explorer").getByRole("alert").filter({ hasText: "saved stability analysis temporarily unavailable" });
  await expect(stabilityError).toBeVisible();
  await stabilityError.getByRole("button", { name: "Retry stability check" }).click();
  await expect(stabilityError).toHaveCount(0);
  expect(stabilityReads).toBe(2);
});

test("late artifact inventory from a closed project is ignored after switching projects", async ({ page }) => {
  const firstPath = join(tmpdir(), `ruflex-artifact-switch-a-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const secondPath = join(tmpdir(), `ruflex-artifact-switch-b-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const oldArtifactSha = "a".repeat(64);
  let releaseFirstRead!: () => void;
  const firstReadGate = new Promise<void>((resolve) => { releaseFirstRead = resolve; });
  let artifactReads = 0;
  await page.route("**/api/projects/*/artifacts", async (route) => {
    artifactReads += 1;
    if (artifactReads === 1) {
      await firstReadGate;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ sha256: oldArtifactSha, size_bytes: 123, source_kind: "dataset", media_type: "text/csv" }]) });
    }
    return route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(firstPath);
  await page.getByLabel("Project name").fill("Artifact Project A");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect.poll(() => artifactReads).toBe(1);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(secondPath);
  await page.getByLabel("Project name").fill("Artifact Project B");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Artifact Project B", exact: true })).toBeVisible();
  releaseFirstRead();
  await expect(page.getByText(oldArtifactSha.slice(0, 12), { exact: false })).toHaveCount(0);
  await expect(page.getByText("No immutable artifacts yet.", { exact: true })).toBeVisible();
});

test("older artifact inventory cannot overwrite a newer post-save refresh", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-artifact-order-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const newerArtifactSha = "b".repeat(64);
  let releaseInitialRead!: () => void;
  const initialReadGate = new Promise<void>((resolve) => { releaseInitialRead = resolve; });
  let artifactReads = 0;
  await page.route("**/api/projects/*/artifacts", async (route) => {
    artifactReads += 1;
    if (artifactReads === 1) {
      await initialReadGate;
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ sha256: newerArtifactSha, size_bytes: 456, source_kind: "dataset", media_type: "text/csv" }]) });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Artifact order");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect.poll(() => artifactReads).toBe(1);
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill("x,target\n1,0\n2,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(newerArtifactSha.slice(0, 12), { exact: false })).toBeVisible();
  expect(artifactReads).toBe(2);
  releaseInitialRead();
  await expect(page.getByText(newerArtifactSha.slice(0, 12), { exact: false })).toBeVisible();
  await expect(page.getByText("No immutable artifacts yet.", { exact: true })).toHaveCount(0);
});
