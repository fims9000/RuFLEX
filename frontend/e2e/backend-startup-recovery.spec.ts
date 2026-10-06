import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("project actions recover after the backend becomes available", async ({ page }) => {
  let healthChecks = 0;
  const projectCreateRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/projects")) projectCreateRequests.push(request.url());
  });
  await page.route("**/api/health", async (route) => {
    healthChecks += 1;
    if (healthChecks === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporarily unavailable" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) });
  });

  await page.goto("/");
  const unavailable = page.getByTestId("backend-unavailable");
  await expect(unavailable).toContainText("The RuFLEX backend is unavailable");
  await expect(page.getByRole("button", { name: "Create project", exact: true })).toBeDisabled();
  const projectPath = join(tmpdir(), `ruflex-backend-recovery-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Backend recovery project");
  await page.getByLabel("Project name").press("Enter");
  expect(projectCreateRequests).toEqual([]);
  await unavailable.getByRole("button", { name: "Retry backend connection" }).click();

  await expect(page.getByRole("button", { name: "Create project", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Backend recovery project", exact: true })).toBeVisible();
  expect(projectCreateRequests).toHaveLength(1);
});
