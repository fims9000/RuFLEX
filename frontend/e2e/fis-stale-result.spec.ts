import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("FIS output is not presented as current after inputs change", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-result-${Date.now()}`);
  let evaluationRequests = 0;
  await page.route("**/api/projects/fis/evaluate", async (route) => {
    evaluationRequests += 1;
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

  await page.getByRole("button", { name: "Evaluate", exact: true }).click();
  const output = page.locator(".result-card").filter({ has: page.getByText("OUTPUT", { exact: true }) });
  await expect(output).toBeVisible();
  await page.getByLabel("temperature", { exact: true }).fill("21");
  await expect(page.getByText("The displayed FIS result belongs to another model revision or input sample.", { exact: false })).toBeVisible();
  await expect(output).toHaveCount(0);
  await page.getByLabel("temperature", { exact: true }).fill("not numeric");
  await page.getByRole("button", { name: "Evaluate", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Invalid: temperature" })).toBeVisible();
  expect(evaluationRequests).toBe(1);
});
