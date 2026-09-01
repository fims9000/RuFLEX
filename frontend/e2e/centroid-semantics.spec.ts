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
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Risk FIS.*mamdani/ }).click();
  await expect(page.getByLabel("Centroid sampling")).toHaveValue("inclusive_nodes");
});
