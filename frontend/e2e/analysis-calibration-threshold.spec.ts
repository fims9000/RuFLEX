import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-analysis-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function trainingCsv(): string {
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 80; index += 1) {
    const temperature = 8 + index * 0.55;
    const torque = 12 + (index * 13) % 75;
    const target = temperature + torque > 64 ? 1 : 0;
    rows.push(`${temperature.toFixed(2)},${torque.toFixed(2)},${target}`);
  }
  return `${rows.join("\n")}\n`;
}

test("PRODUCT-04 persists validation calibration and decision-threshold provenance", async ({ page }) => {
  test.setTimeout(60_000);
  const path = projectPath();

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Calibration route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();

  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();

  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });

  await page.getByRole("button", { name: "A", exact: true }).click();
  await page.getByRole("button", { name: "Save validation evidence", exact: true }).click();
  await expect(page.getByText(/validation rows persisted/)).toBeVisible();

  await page.getByRole("button", { name: "Fit validation calibration", exact: true }).click();
  await expect(page.getByText("Brier calibrated", { exact: true })).toBeVisible();
  await expect(page.getByText(/Platt transform/)).toBeVisible();

  await page.getByRole("button", { name: "Select F1 threshold (calibrated)", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Probability → calibration → threshold → class", exact: true })).toBeVisible();
  await expect(page.getByText(/Final-test data remain locked/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Calibration transform.*platt_scaling.*validation/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Decision threshold.*calibrated/ })).toBeVisible();

  await page.getByText(/I confirm this policy was frozen before final-test access/).click();
  await page.getByRole("button", { name: "Evaluate frozen final test", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Final-test evidence persisted separately", exact: true })).toBeVisible();
  await expect(page.getByText(/final-test rows evaluated with frozen policy/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Final-test evaluation.*frozen policy/ })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("Brier calibrated", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Probability → calibration → threshold → class", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Final-test evidence persisted separately", exact: true })).toBeVisible();
  await expect(page.getByText(/final-test rows evaluated with frozen policy/)).toBeVisible();
});

test("PRODUCT-07 persists a validation-only ACCEPT / REVIEW policy separately from class threshold", async ({ page }) => {
  test.setTimeout(60_000);
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Selective route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByRole("button", { name: "A", exact: true }).click();
  await page.getByRole("button", { name: "Save validation evidence", exact: true }).click();
  await page.getByRole("button", { name: /Select F1 threshold \(raw\)/, exact: true }).click();
  await page.getByLabel("Selective confidence cutoff").fill("0.80");
  await page.getByRole("button", { name: "Save ACCEPT / REVIEW policy", exact: true }).click();
  await expect(page.getByText("REVIEW BELOW 0.80", { exact: false })).toBeVisible();
  await expect(page.getByText(/class threshold/)).toHaveCount(2);
  await expect(page.getByText(/independent of the class threshold/)).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("REVIEW BELOW 0.80", { exact: false })).toBeVisible();
});

test("PRODUCT-11 runs the safe condition-monitoring telemetry decision route", async ({ page }) => {
  test.setTimeout(60_000); const path = projectPath();
  await page.goto("/"); await page.getByLabel("Project path").fill(path); await page.getByLabel("Project name").fill("Condition monitoring"); await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click(); await page.getByLabel("CSV data").fill(trainingCsv()); await page.getByRole("button", { name: "Inspect dataset", exact: true }).click(); await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click(); await page.getByLabel("Training model").selectOption("logistic_regression"); await page.getByRole("button", { name: "Run real training", exact: true }).click(); await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByRole("button", { name: "A", exact: true }).click(); await page.getByRole("button", { name: "Save validation evidence", exact: true }).click(); await page.getByRole("button", { name: /Select F1 threshold \(raw\)/ }).click(); await page.getByRole("button", { name: "Save ACCEPT / REVIEW policy", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click(); await page.getByRole("button", { name: "Run telemetry demonstration", exact: true }).click(); await expect(page.getByTestId("condition-monitoring-demo")).toContainText(/ACCEPT|REVIEW|OUT_OF_SCOPE/); await expect(page.getByTestId("condition-monitoring-demo")).toContainText(/no actuator command/i);
  await page.getByRole("button", { name: "Close", exact: true }).click(); await page.getByLabel("Project path").fill(path); await page.getByRole("button", { name: "Open project", exact: true }).click(); await page.getByRole("button", { name: "E", exact: true }).click(); await expect(page.getByTestId("condition-monitoring-demo")).toContainText(/ACCEPT|REVIEW|OUT_OF_SCOPE/);
});
