import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("compact Studio keeps every workbench and optional panel reachable", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-compact-studio-${Date.now()}`);
  await page.setViewportSize({ width: 920, height: 720 });
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Compact Studio route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();

  await expect(page.locator(".bottom-panel")).toBeHidden();
  await expect(page.locator(".inspector")).toBeHidden();
  const navigation = page.getByRole("navigation", { name: "Workbench navigation" });
  for (const section of ["PROJECT", "DATA", "MODELS", "STUDIES", "ANALYSES", "EVIDENCE"]) {
    const item = navigation.getByTitle(section);
    await expect(item).toBeVisible();
    await item.click();
    await expect(item).toHaveAttribute("aria-current", "page");
  }
  await expect(page.locator(".workspace-header h1")).toHaveText("Evidence");
  await page.getByRole("button", { name: "Show properties" }).click();
  await expect(page.locator(".inspector")).toBeVisible();
  await page.getByRole("button", { name: "Hide properties" }).click();
  await page.getByRole("button", { name: "Show jobs panel" }).click();
  await expect(page.locator(".bottom-panel")).toBeVisible();
  await page.getByRole("button", { name: "Hide jobs panel" }).click();
  await navigation.getByTitle("PROJECT").click();
  await expect(page.getByRole("region", { name: "Optional quick start" })).toBeVisible();
  await expect(page.locator(".project-object-tree")).not.toContainText("Checking");
  await page.mouse.move(0, 0);
  await expect(page).toHaveScreenshot("compact-studio-920.png", { fullPage: true, animations: "disabled" });

  await page.setViewportSize({ width: 640, height: 720 });
  await page.getByRole("button", { name: "Hide project explorer" }).click();
  await expect(page.locator(".explorer")).toBeHidden();
  await page.getByRole("button", { name: "Show project explorer" }).click();
  await expect(page.locator(".explorer")).toBeVisible();
  await page.getByRole("button", { name: "Hide project explorer" }).click();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.mouse.move(0, 0);
  await expect(page).toHaveScreenshot("compact-studio-640.png", { fullPage: true, animations: "disabled" });
});
