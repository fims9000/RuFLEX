import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("default FIS creation disables duplicate requests while the model is being created", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-create-${Date.now()}`);
  let createRequests = 0;
  let saveRequests = 0;
  await page.route("**/api/projects/fis/default", async (route) => {
    createRequests += 1;
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.continue();
  });
  await page.route("**/api/projects/fis/save", async (route) => {
    saveRequests += 1;
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS creation guard");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();

  const createButton = page.getByRole("button", { name: "Create FIS from dataset", exact: true });
  await createButton.click();
  await expect(page.getByRole("button", { name: "Creating FIS…", exact: true })).toBeDisabled();
  expect(createRequests).toBe(1);
  await expect(page.getByRole("button", { name: /Risk FIS.*mamdani/ })).toBeVisible();
  expect(createRequests).toBe(1);

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByRole("button", { name: "Saving FIS…", exact: true })).toBeDisabled();
  expect(saveRequests).toBe(1);
  await expect(page.getByRole("button", { name: "Save FIS", exact: true })).toBeEnabled();
  expect(saveRequests).toBe(1);
});
