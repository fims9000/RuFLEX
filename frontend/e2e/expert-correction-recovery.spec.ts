import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function csv(): string {
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 48; index += 1) {
    const temperature = 10 + index * 0.6;
    const torque = 18 + (index * 13) % 58;
    const target = temperature + torque > 58 ? 1 : 0;
    rows.push(`${temperature.toFixed(2)},${torque.toFixed(2)},${target}`);
  }
  return `${rows.join("\n")}\n`;
}

test("PRODUCT-13 recovers a persisted TRAIN-only Sugeno correction without refitting", async ({ page }) => {
  test.setTimeout(45_000);
  const path = join(tmpdir(), `ruflex-expert-refit-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Expert correction recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(csv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await page.getByLabel("FIS family").selectOption("sugeno");
  const consequents = page.getByLabel(/Rule .* Sugeno value/);
  await expect(consequents).toHaveCount(3);
  for (let index = 0; index < await consequents.count(); index += 1) await consequents.nth(index).fill("0.5");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByText(/Canonical executable FIS saved with a semantic hash/)).toBeVisible();

  let correctionPosts = 0;
  let savedFirstConsequent: number | undefined;
  await page.route("**/api/projects/fis/save", async (route) => {
    if (route.request().method() === "POST") savedFirstConsequent = route.request().postDataJSON().spec.rules[0].sugeno_consequent.constant;
    return route.continue();
  });
  await page.route("**/api/projects/fis/expert-correction", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    correctionPosts += 1;
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Expert correction response lost after persistence" }) });
  });
  let releaseRecovery: () => void = () => {};
  let recoveryStarted: () => void = () => {};
  const recoveryStartedPromise = new Promise<void>((resolve) => { recoveryStarted = resolve; });
  await page.route("**/fis/expert-correction/latest", async (route) => {
    const response = await route.fetch();
    recoveryStarted();
    await new Promise<void>((resolve) => { releaseRecovery = resolve; });
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Refit unlocked consequents on TRAIN", exact: true }).evaluate((button) => { button.dispatchEvent(new MouseEvent("click", { bubbles: true })); button.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  const recovery = page.getByTestId("expert-refit-recovery");
  await expect(recovery).toContainText("Expert correction response lost after persistence");
  await page.getByRole("button", { name: "Retry exact correction lookup", exact: true }).click();
  await recoveryStartedPromise;
  await page.getByLabel("Rule 1 Sugeno value", { exact: true }).fill("0.6");
  await page.getByLabel("Rule 1 Sugeno value", { exact: true }).blur();
  releaseRecovery();
  await expect(recovery).toHaveCount(0);
  expect(correctionPosts).toBe(1);
  await expect(page.getByText(/Recovered the exact TRAIN-only expert correction; newer editor changes remain unsaved/)).toBeVisible();
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedFirstConsequent).toBe(0.6);
});

test("TRAIN-only correction completion preserves a newer Sugeno editor draft", async ({ page }) => {
  test.setTimeout(45_000);
  const path = join(tmpdir(), `ruflex-expert-draft-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  let releaseCorrection: () => void = () => {};
  let correctionStarted: () => void = () => {};
  const correctionStartedPromise = new Promise<void>((resolve) => { correctionStarted = resolve; });
  let savedFirstConsequent: number | undefined;

  await page.route("**/api/projects/fis/save", async (route) => {
    if (route.request().method() === "POST") {
      const spec = route.request().postDataJSON().spec;
      savedFirstConsequent = spec.rules[0].sugeno_consequent.constant;
    }
    return route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Expert correction draft preservation");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(csv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await page.getByLabel("FIS family").selectOption("sugeno");
  const consequents = page.getByLabel(/Rule .* Sugeno value/);
  for (let index = 0; index < await consequents.count(); index += 1) await consequents.nth(index).fill("0.5");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByText(/Canonical executable FIS saved with a semantic hash/)).toBeVisible();

  await page.route("**/api/projects/fis/expert-correction", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    correctionStarted();
    await new Promise<void>((resolve) => { releaseCorrection = resolve; });
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Refit unlocked consequents on TRAIN", exact: true }).click();
  await correctionStartedPromise;
  const firstConsequent = page.getByLabel("Rule 1 Sugeno value", { exact: true });
  await firstConsequent.fill("0.75");
  await firstConsequent.blur();
  await expect(firstConsequent).toHaveValue("0.75");
  releaseCorrection();

  await expect(firstConsequent).toHaveValue("0.75");
  await expect(page.getByText(/newer editor changes remain unsaved/)).toBeVisible();
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect.poll(() => savedFirstConsequent).toBe(0.75);
});

test("an in-flight FIS save blocks a concurrent TRAIN-only expert refit", async ({ page }) => {
  test.setTimeout(45_000);
  const path = join(tmpdir(), `ruflex-fis-save-refit-mutex-${Date.now()}`);
  let releaseSave: () => void = () => {};
  let saveStarted: () => void = () => {};
  const saveStartedPromise = new Promise<void>((resolve) => { saveStarted = resolve; });
  let savePosts = 0;
  let refitPosts = 0;

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("FIS save refit mutex");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(csv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await page.getByLabel("FIS family").selectOption("sugeno");
  const consequents = page.getByLabel(/Rule .* Sugeno value/);
  for (let index = 0; index < await consequents.count(); index += 1) await consequents.nth(index).fill("0.5");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await expect(page.getByText(/Canonical executable FIS saved with a semantic hash/)).toBeVisible();

  await page.route("**/api/projects/fis/save", async (route) => {
    if (route.request().method() === "POST") {
      savePosts += 1;
      const response = await route.fetch();
      saveStarted();
      await new Promise<void>((resolve) => { releaseSave = resolve; });
      await route.fulfill({ response });
      return;
    }
    await route.continue();
  });
  await page.route("**/api/projects/fis/expert-correction", async (route) => {
    if (route.request().method() === "POST") refitPosts += 1;
    await route.continue();
  });

  await page.getByLabel("Rule 1 Sugeno value", { exact: true }).fill("0.6");
  await page.getByLabel("Rule 1 Sugeno value", { exact: true }).blur();
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await saveStartedPromise;

  const refit = page.getByRole("button", { name: "Refit unlocked consequents on TRAIN", exact: true });
  await expect(refit).toBeDisabled();
  await refit.evaluate((button) => button.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  await page.waitForTimeout(100);
  expect(refitPosts).toBe(0);
  expect(savePosts).toBe(1);

  releaseSave();
  await expect(page.getByText("Canonical executable FIS saved with a semantic hash.", { exact: true })).toBeVisible();
  expect(refitPosts).toBe(0);
  expect(savePosts).toBe(1);
});
