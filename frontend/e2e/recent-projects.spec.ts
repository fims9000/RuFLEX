import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("recent project history reopens local projects after a browser reload and can be cleared", async ({ page }) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const path = join(tmpdir(), `ruflex-recent-project-${suffix}`);
  const secondPath = join(tmpdir(), `ruflex-recent-project-second-${suffix}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Recent Alpha project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recent Alpha project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByRole("region", { name: "Recent projects" })).toBeVisible();
  await page.getByLabel("Project path").fill(secondPath);
  await page.getByLabel("Project name").fill("Second recent project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Close", exact: true }).click();

  await page.reload();
  const recent = page.getByRole("region", { name: "Recent projects" });
  await expect(recent).toContainText(path);
  await recent.getByRole("button", { name: "Forget Recent Alpha project", exact: true }).click();
  await expect(recent).not.toContainText("Recent Alpha project");
  await expect(recent).toContainText("Second recent project");
  await recent.locator(".recent-project-item").filter({ hasText: "Second recent project" }).click();
  await expect(page.getByRole("heading", { name: "Second recent project", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("region", { name: "Recent projects" }).getByRole("button", { name: "Forget history", exact: true }).click();
  await expect(page.getByRole("region", { name: "Recent projects" })).toHaveCount(0);
});

test("a missing recent project explains recovery and clears stale errors when history is replaced", async ({ page }) => {
  const missingPath = join(tmpdir(), `ruflex-missing-recent-project-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.addInitScript((path) => {
    localStorage.setItem("ruflex.recent-projects.v1", JSON.stringify([{ name: "Moved project", path }]));
  }, missingPath);

  await page.goto("/");
  const recent = page.getByRole("region", { name: "Recent projects" });
  await recent.locator(".recent-project-item").click();
  await expect(recent.getByRole("alert")).toContainText("choose the folder again");
  await recent.getByRole("button", { name: "Forget Moved project", exact: true }).click();
  await expect(recent).toHaveCount(0);

  const replacementPath = join(tmpdir(), `ruflex-replacement-project-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.getByLabel("Project path").fill(replacementPath);
  await page.getByLabel("Project name").fill("Replacement project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Replacement project", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Recent projects" }).getByRole("alert")).toHaveCount(0);
});
