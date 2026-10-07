import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("FIS output is bound to the saved model revision and exact inputs", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-result-${Date.now()}`);
  let evaluationRequests = 0;
  await page.route("**/api/projects/fis/evaluate", async (route) => {
    evaluationRequests += 1;
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.continue();
  });
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS result identity");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  await page.getByRole("button", { name: "Evaluate", exact: true }).dblclick({ delay: 20 });
  const output = page.locator(".result-card").filter({ has: page.getByText("OUTPUT", { exact: true }) });
  await expect(output).toBeVisible();
  await page.getByLabel("Resolution", { exact: true }).fill("51");
  await expect(page.getByText("The displayed FIS result belongs to another model revision or input sample.", { exact: false })).toBeVisible();
  await expect(output).toHaveCount(0);
  await expect(page.getByText("Save this FIS revision before evaluating or exporting; both operations use the active persisted model.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeDisabled();
  await expect(page.locator('[data-ruflex-action="fis.evaluate"]')).toBeDisabled();
  await expect(page.getByRole("button", { name: "Export MATLAB .fis", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByText("Canonical executable FIS saved with a semantic hash.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Export MATLAB .fis", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Evaluate", exact: true }).click();
  await expect(output).toBeVisible();
  await page.getByLabel("temperature", { exact: true }).fill("21");
  await expect(page.getByText("The displayed FIS result belongs to another model revision or input sample.", { exact: false })).toBeVisible();
  await expect(output).toHaveCount(0);
  await page.getByLabel("temperature", { exact: true }).fill("not numeric");
  await page.getByRole("button", { name: "Evaluate", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Invalid: temperature" })).toBeVisible();
  expect(evaluationRequests).toBe(2);
});
