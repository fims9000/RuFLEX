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
  await page.route("**/api/projects/fis/expert-correction", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    correctionPosts += 1;
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Expert correction response lost after persistence" }) });
  });
  await page.getByRole("button", { name: "Refit unlocked consequents on TRAIN", exact: true }).evaluate((button) => { button.dispatchEvent(new MouseEvent("click", { bubbles: true })); button.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  const recovery = page.getByTestId("expert-refit-recovery");
  await expect(recovery).toContainText("Expert correction response lost after persistence");
  await page.getByRole("button", { name: "Retry exact correction lookup", exact: true }).click();
  await expect(recovery).toHaveCount(0);
  expect(correctionPosts).toBe(1);
  await expect(page.getByText(/TRAIN RMSE .* →/)).toBeVisible();
});
