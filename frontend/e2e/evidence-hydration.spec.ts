import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("saved tree-path hydration distinguishes unavailable from absent and can be retried", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-evidence-hydration-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Evidence hydration");
  await page.getByRole("button", { name: "Create project", exact: true }).click();

  let latestReads = 0;
  await page.route("**/api/projects/*/evidence/tree-path/latest", async (route) => {
    latestReads += 1;
    if (latestReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved tree path temporarily unavailable" }) });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "no saved tree path" }) });
  });
  await page.getByTitle("EVIDENCE").click();
  const hydrationError = page.getByTestId("tree-evidence-hydration-error");
  await expect(hydrationError).toContainText("saved tree path temporarily unavailable");
  await hydrationError.getByRole("button", { name: "Retry structural trace" }).click();
  await expect(hydrationError).toHaveCount(0);
  await expect(page.getByTestId("tree-evidence-empty")).toBeVisible();
  expect(latestReads).toBe(2);
});
