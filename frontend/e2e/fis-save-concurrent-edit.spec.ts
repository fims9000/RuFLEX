import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("edits made during a save remain as an unsaved draft", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-fis-save-race-${Date.now()}`);
  const savedSpecs: Array<{ operators: { centroid_resolution: number } }> = [];
  let releaseFirstSave: () => void = () => {};
  let firstSaveStarted: () => void = () => {};
  const firstSaveStartedPromise = new Promise<void>((resolve) => { firstSaveStarted = resolve; });
  await page.route("**/api/projects/fis/save", async (route) => {
    savedSpecs.push(route.request().postDataJSON().spec as { operators: { centroid_resolution: number } });
    if (savedSpecs.length === 1) {
      firstSaveStarted();
      await new Promise<void>((resolve) => { releaseFirstSave = resolve; });
    }
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("FIS save race");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await firstSaveStartedPromise;
  const resolution = page.getByLabel("Resolution", { exact: true });
  const editedResolution = Number(await resolution.inputValue()) + 1;
  await resolution.fill(String(editedResolution));
  await expect(resolution).toHaveValue(String(editedResolution));
  releaseFirstSave();
  await expect(page.getByText("The submitted FIS revision was saved; newer editor changes remain unsaved.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedSpecs.length).toBe(2);
  await expect(page.getByText("Canonical executable FIS saved with a semantic hash.", { exact: true })).toBeVisible();
  expect(savedSpecs[1].operators.centroid_resolution).toBe(editedResolution);
  await expect(page.getByRole("button", { name: "Evaluate", exact: true })).toBeEnabled();
});
