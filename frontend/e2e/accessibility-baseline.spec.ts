import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-a11y-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

async function assertBaseline(page: Page, workspace: string): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter((violation) => ["critical", "serious"].includes(violation.impact ?? ""));
  expect(blocking, `${workspace}: ${blocking.map((item) => item.id).join(", ")}`).toEqual([]);
}

test("accessibility baseline covers the primary Studio workspaces", async ({ page }) => {
  const path = projectPath();
  await page.goto("/");
  await assertBaseline(page, "Project");

  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Accessibility baseline");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  const navigation = page.getByRole("navigation", { name: "Workbench navigation" });
  await expect(navigation.getByRole("button", { name: "P", exact: true })).toHaveAttribute("aria-description", "Open project workspace");
  await expect(navigation.getByRole("button", { name: "P", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(navigation.getByRole("button", { name: "A", exact: true })).not.toHaveAttribute("aria-current");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill("x,target\n1,0\n2,1\n3,0\n4,1\n5,0\n6,1\n7,0\n8,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await assertBaseline(page, "Data");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await page.getByTitle("STUDIES").click();
  await expect(page.getByText("REAL TRAINING ENGINE", { exact: true })).toBeVisible();
  await assertBaseline(page, "Training and Stability Lab");

  await page.getByTitle("ANALYSES").click();
  await expect(navigation.getByRole("button", { name: "A", exact: true })).toHaveAttribute("aria-current", "page");
  await assertBaseline(page, "Evaluation");
  await page.getByTitle("EVIDENCE").click();
  await assertBaseline(page, "Evidence Assurance and Bundle");
});
