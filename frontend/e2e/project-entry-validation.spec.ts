import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("project entry validates required inputs and guides duplicate paths to open", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByTestId("project-form-error")).toContainText("Enter a project folder path");

  const projectPath = join(tmpdir(), `ruflex-project-entry-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Existing project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Existing project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();

  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Duplicate name");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByTestId("project-form-error")).toContainText("Choose Open project to reopen it");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Existing project", exact: true })).toBeVisible();
});
