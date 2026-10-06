import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(name: string): string {
  return join(tmpdir(), `ruflex-dataset-session-race-${name}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

test("a dataset confirmation response from a closed project cannot hydrate the next project", async ({ page }) => {
  test.setTimeout(25_000);
  const sourcePath = projectPath("source");
  const nextPath = projectPath("next");
  const createdNext = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path: nextPath, name: "Next empty project" } });
  expect(createdNext.status()).toBe(201);

  let releaseConfirmation!: () => void;
  let markConfirmationPersisted!: () => void;
  const confirmationGate = new Promise<void>((resolve) => { releaseConfirmation = resolve; });
  const confirmationPersisted = new Promise<void>((resolve) => { markConfirmationPersisted = resolve; });
  await page.route("**/api/projects/dataset/confirm", async (route) => {
    const response = await route.fetch();
    markConfirmationPersisted();
    await confirmationGate;
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(sourcePath);
  await page.getByLabel("Project name").fill("Source dataset project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill("temperature,target\n10,0\n20,1\n30,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await confirmationPersisted;

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(nextPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.locator(".data-workspace")).toContainText("This CSV is an editable draft only");

  try {
    const confirmationResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/dataset/confirm") && response.request().method() === "POST",
    );
    releaseConfirmation();
    await confirmationResponse;
    await expect(page.getByRole("heading", { name: "Next empty project", exact: true })).toBeVisible();
    await expect(page.locator(".data-workspace")).toContainText("This CSV is an editable draft only");
    await expect(page.getByText(/Contract: target/)).toHaveCount(0);
  } finally {
    releaseConfirmation();
  }
});
