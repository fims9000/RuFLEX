import { expect, test } from "@playwright/test";

test.describe("P0 visual foundation", () => {
  test("light shell, minimum viewport, collapsed panels and keyboard focus", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page).toHaveScreenshot("light-shell-1440x900.png", { fullPage: true, animations: "disabled" });
    await page.getByLabel("Collapse explorer").click();
    await page.getByLabel("Collapse properties").click();
    await page.getByLabel("Collapse jobs panel").click();
    await page.setViewportSize({ width: 1180, height: 720 });
    await page.keyboard.press("Tab");
    await expect(page.locator(":focus")).toBeVisible();
    await expect(page).toHaveScreenshot("minimum-collapsed-focus.png", { fullPage: true, animations: "disabled" });
  });

  test("dark shell and controlled offline error", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await page.getByLabel("Toggle theme").click();
    await expect(page).toHaveScreenshot("dark-shell-1440x900.png", { fullPage: true, animations: "disabled" });
    await page.route("**/api/health", (route) => route.abort());
    await page.reload();
    await expect(page.locator(".error")).toBeVisible();
    await expect(page).toHaveScreenshot("offline-error.png", { fullPage: true, animations: "disabled" });
  });
});
