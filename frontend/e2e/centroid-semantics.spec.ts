import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("CENTROID-01 exposes midpoint sampling and persists an explicit legacy selection", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-centroid-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Centroid semantics");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await expect(page.getByLabel("Centroid sampling")).toHaveValue("midpoint_cells");
  await expect(page.getByText("Midpoint cells samples the center of each discretization interval.", { exact: false })).toBeVisible();
  await page.getByLabel("Centroid sampling").selectOption("inclusive_nodes");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  let traceReads = 0;
  await page.route("**/fis/trace/latest", async (route) => {
    traceReads += 1;
    if (traceReads === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved FIS trace temporarily unavailable" }) });
    return route.continue();
  });
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Risk FIS.*mamdani/ }).click();
  await expect(page.getByLabel("Centroid sampling")).toHaveValue("inclusive_nodes");
  const traceError = page.getByRole("alert").filter({ hasText: "Could not load saved FIS evaluation evidence" });
  await expect(traceError).toContainText("saved FIS trace temporarily unavailable");
  await expect(traceError).toBeVisible();
  await traceError.getByRole("button", { name: "Retry FIS trace check", exact: true }).click();
  await expect(page.getByText("No saved exact FIS trace is available yet.", { exact: true })).toBeVisible();
  expect(traceReads).toBe(2);
});
