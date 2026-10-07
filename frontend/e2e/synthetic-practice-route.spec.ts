import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("a first-time user can turn the synthetic practice draft into a persisted training run", async ({ page }) => {
  test.setTimeout(45_000);
  const path = join(tmpdir(), `ruflex-practice-route-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Practice route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();

  const practice = page.getByRole("group", { name: "Synthetic practice dataset" });
  await expect(practice).toContainText("not research evidence");
  await practice.getByRole("button", { name: "Load synthetic practice CSV (80 rows)" }).click();
  await expect(page.getByLabel("CSV data")).toContainText("practice-080");
  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 80 · columns: 4/)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "ID columns" })).toHaveValue("entity_id");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(/Contract: target · binary_classification/)).toBeVisible();
  await expect(practice).toHaveCount(0);
  const frozenSha = await page.locator(".data-summary code").first().textContent();
  expect(frozenSha).toBe("37b5f2a3872ec570bacd35d8e031bc8336c18db744989df332a58d827cc08399");
  await expect(page.getByTestId("synthetic-practice-provenance")).toContainText("not benchmark or research evidence");

  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  const response = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/run") && item.request().method() === "POST");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  expect((await response).status()).toBe(201);
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted");

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "target 80 rows", exact: true }).click();
  await expect(page.locator(".data-summary code").first()).toHaveText(frozenSha ?? "");
  await expect(page.getByText("Stored dataset preview", { exact: true })).toBeVisible();
  await expect(page.getByTestId("synthetic-practice-provenance")).toContainText("synthetic practice fixture");
  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted");
});

test("synthetic practice loading is unavailable in a read-only project", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-practice-readonly-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Read-only practice");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("checkbox", { name: "Read-only", exact: true }).check();
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await expect(page.getByRole("group", { name: "Synthetic practice dataset" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeDisabled();
});
