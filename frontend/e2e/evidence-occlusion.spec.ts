import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-evidence-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function trainingCsv(): string {
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 40; index += 1) {
    const temperature = 10 + index * 0.8;
    const torque = 20 + (index * 9) % 60;
    rows.push(`${temperature.toFixed(2)},${torque.toFixed(2)},${temperature + torque > 60 ? 1 : 0}`);
  }
  return `${rows.join("\n")}\n`;
}

test("PRODUCT-05 persists post-hoc evidence separately from exact traces", async ({ page }) => {
  test.setTimeout(60_000);
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Evidence route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });

  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByText("Computation evidence and post-hoc attribution", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Generate explanation", exact: true }).click();
  await expect(page.getByTestId("explanation-job")).toContainText("SUCCEEDED");
  await expect(page.getByText("POST-HOC ATTRIBUTION", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/not a causal effect/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Run explanation checks", exact: true }).click();
  await expect(page.getByText("PASSED_AVAILABLE_CHECKS", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Post-hoc occlusion/ }).click();
  await expect(page.getByTestId("explanation-job")).toContainText("SUCCEEDED");
  await expect(page.getByText("PASSED_AVAILABLE_CHECKS", { exact: true })).toBeVisible();
});

test("PRODUCT-06 persists revision-bound BehaviorSpec evidence through reopen", async ({ page }) => {
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Behavior route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByRole("button", { name: "E", exact: true }).click();
  await page.getByRole("button", { name: "Create and run BehaviorSpec", exact: true }).click();
  await expect(page.getByTestId("behavior-result").getByText("PASS")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/artifact [0-9a-f]{12}/)).toBeVisible();
  await page.getByLabel("Behavior spec type").selectOption("monotonic_pair");
  await page.getByLabel("Behavior comparison temperature").fill("100");
  await page.getByRole("button", { name: "Create and run BehaviorSpec", exact: true }).click();
  await expect(page.getByTestId("behavior-result")).toContainText("expected nondecreasing", { timeout: 15_000 });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByTestId("behavior-result").getByText("PASS")).toBeVisible({ timeout: 15_000 });
});
