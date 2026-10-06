import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-fis-unmounted-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

test("a persisted FIS response from an unmounted workbench cannot hydrate the next project", async ({ page }) => {
  test.setTimeout(25_000);
  const firstPath = projectPath("source");
  const secondPath = projectPath("next");
  const nextCreated = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path: secondPath, name: "Next FIS-free project" } });
  expect(nextCreated.status()).toBe(201);

  await page.goto("/");
  await page.getByLabel("Project path").fill(firstPath);
  await page.getByLabel("Project name").fill("FIS source project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "M", exact: true }).click();

  let releaseCreation!: () => void;
  let markCreationPersisted!: () => void;
  const creationGate = new Promise<void>((resolve) => { releaseCreation = resolve; });
  const creationPersisted = new Promise<void>((resolve) => { markCreationPersisted = resolve; });
  await page.route("**/api/projects/fis/default", async (route) => {
    const response = await route.fetch();
    markCreationPersisted();
    await creationGate;
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await creationPersisted;

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(secondPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "M", exact: true }).click();

  try {
    const creationResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/fis/default") && response.request().method() === "POST",
    );
    releaseCreation();
    await creationResponse;
    await expect(page.getByText("No FIS model", { exact: true })).toBeVisible();
    await expect(page.getByText("FIS source project", { exact: true })).toHaveCount(0);
  } finally {
    releaseCreation();
  }
});
