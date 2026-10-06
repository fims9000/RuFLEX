import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("recent project history reopens local projects after a browser reload and can be cleared", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-recent-project-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Recent Alpha project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recent Alpha project", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByRole("region", { name: "Recent projects" })).toBeVisible();

  await page.reload();
  const recent = page.getByRole("region", { name: "Recent projects" });
  await expect(recent).toContainText(path);
  await recent.getByRole("button", { name: /Recent Alpha project/ }).click();
  await expect(page.getByRole("heading", { name: "Recent Alpha project", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("region", { name: "Recent projects" }).getByRole("button", { name: "Forget history", exact: true }).click();
  await expect(page.getByRole("region", { name: "Recent projects" })).toHaveCount(0);
});
