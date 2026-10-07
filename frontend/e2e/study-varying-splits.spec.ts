import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("a varying-split Study does not reuse a previously frozen fixed SplitContract", async ({ page }) => {
  test.setTimeout(60_000);
  const path = join(tmpdir(), `ruflex-varying-split-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const rows = ["x,y,target"];
  for (let index = 0; index < 80; index += 1) {
    const x = index % 20;
    const y = Math.floor(index / 20) * 3;
    rows.push(`${x},${y},${x + y >= 14 ? 1 : 0}`);
  }

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Varying split practice");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(`${rows.join("\n")}\n`);
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByRole("button", { name: "Freeze RANDOM SplitContract", exact: true }).click();
  await expect(page.getByRole("button", { name: "SplitContract frozen", exact: true })).toBeVisible();

  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByLabel("Study randomness protocol").selectOption("SPLIT_VARIABILITY");
  await page.getByLabel("Split family").selectOption("GROUP");
  await expect(page.getByRole("button", { name: "Run multi-seed study", exact: true })).toBeDisabled();
  await expect(page.getByText(/Choose RANDOM split family for this Study protocol/)).toBeVisible();
  await page.getByLabel("Split family").selectOption("RANDOM");
  await page.getByLabel("Split seed").fill("99");
  await page.getByLabel("Single-run training seed").fill("5");
  await page.getByLabel("Study seeds").fill("11, 13, 17");
  await expect(page.getByText(/runs do not reuse the project's active SplitContract/)).toBeVisible();
  const submission = page.waitForResponse((response) => response.url().endsWith("/api/projects/training/study-jobs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  const response = await submission;
  expect(response.status()).toBe(202);
  expect(response.request().postDataJSON()).toMatchObject({ randomness_protocol: "SPLIT_VARIABILITY", seeds: [11, 13, 17], split_seed: null, training_seed: 5, split_contract_id: null });
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/Split variability fixes the training seed but changes split membership/)).toBeVisible();
  for (const splitSeed of [11, 13, 17]) {
    await expect(page.getByRole("button", { name: new RegExp(`SeedRun split ${splitSeed} · train 5`) })).toBeVisible();
  }
  await expect(page.getByText(/split 11 \/ train 5: SUCCEEDED/)).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Study .*3 seed runs/ }).click();
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible();
  await expect(page.getByText(/Split variability fixes the training seed but changes split membership/)).toBeVisible();
  await expect(page.getByRole("button", { name: /SeedRun split 17 · train 5/ })).toBeVisible();

  await page.getByLabel("Study randomness protocol").selectOption("COMBINED_VARIABILITY");
  await page.getByLabel("Study seeds").fill("3, 7, 9");
  const combinedSubmission = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/study-jobs") && item.request().method() === "POST");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  const combinedResponse = await combinedSubmission;
  expect(combinedResponse.status()).toBe(202);
  expect(combinedResponse.request().postDataJSON()).toMatchObject({ randomness_protocol: "COMBINED_VARIABILITY", seeds: [3, 7, 9], split_seed: null, training_seed: null, split_contract_id: null });
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/Combined variability changes both split and training seeds/)).toBeVisible();
  for (const seed of [3, 7, 9]) {
    await expect(page.getByRole("button", { name: new RegExp(`SeedRun split ${seed} · train ${seed}`) })).toBeVisible();
  }
});
