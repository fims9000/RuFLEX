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
  await expect(page.getByTestId("run-capability-negotiation")).toContainText("occlusion");
  await expect(page.getByTestId("run-capability-negotiation")).toContainText("NOT_APPLICABLE");
  await page.getByRole("button", { name: "Generate explanation", exact: true }).click();
  await expect(page.getByTestId("explanation-job")).toContainText("SUCCEEDED");
  await expect(page.getByText("POST-HOC ATTRIBUTION", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/not a causal effect/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Run explanation checks", exact: true }).click();
  await expect(page.getByText("PASSED_AVAILABLE_CHECKS", { exact: true })).toBeVisible();
  await expect(page.getByText("replay integrity", { exact: true })).toBeVisible();
  await expect(page.getByTestId("validator-plugin")).toContainText("native_explanation_validator v1");

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
  await page.getByRole("combobox", { name: "Behavior spec type" }).selectOption("monotonic_pair");
  await page.getByLabel("Behavior comparison temperature").fill("100");
  await page.getByLabel("Name", { exact: true }).fill("Monotonic regression requirement");
  await page.getByRole("button", { name: "Create and run BehaviorSpec", exact: true }).click();
  await expect(page.getByTestId("behavior-result")).toContainText("expected nondecreasing", { timeout: 15_000 });
  await expect(page.getByText(/artifact [0-9a-f]{12}/)).toBeVisible();
  await page.getByRole("button", { name: "Create and run BehaviorSpec", exact: true }).click();
  await expect(page.getByTestId("behavior-result")).toContainText("expected nondecreasing", { timeout: 15_000 });
  const baselineSelector = page.getByRole("combobox", { name: "Behavior baseline result" });
  const candidateSelector = page.getByRole("combobox", { name: "Behavior candidate result" });
  await expect(baselineSelector.locator("option")).toHaveCount(3);
  await expect(candidateSelector.locator("option")).toHaveCount(3);
  await expect(baselineSelector).not.toHaveValue("");
  await expect(candidateSelector).not.toHaveValue("");
  const baselineResultId = await baselineSelector.inputValue();
  const candidateResultId = await candidateSelector.inputValue();
  expect(baselineResultId).not.toBe(candidateResultId);
  await expect(page.getByRole("button", { name: "Compare revisions", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Compare revisions", exact: true }).click();
  await expect(page.getByText("PASS TO PASS", { exact: true })).toBeVisible();
  let latestBehaviorReadFailed = false;
  await page.route(`**/api/projects/*/evidence/behavior-specs/latest`, async (route) => {
    if (!latestBehaviorReadFailed) {
      latestBehaviorReadFailed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary BehaviorSpec read failure" }) });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Temporary BehaviorSpec read failure");
  await page.getByRole("button", { name: "Retry saved BehaviorSpec", exact: true }).click();
  await expect(page.getByTestId("behavior-result")).toContainText("expected nondecreasing", { timeout: 15_000 });
  await page.reload();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByTestId("behavior-result")).toContainText("expected nondecreasing", { timeout: 15_000 });
  await page.getByRole("button", { name: "P", exact: true }).click();
  const persistedResultNode = page.getByTestId(`rf__node-behavior-result:${candidateResultId}`);
  await expect(persistedResultNode).toBeVisible();
  await persistedResultNode.click({ force: true });
  await expect(page.getByTestId("behavior-result")).toContainText("expected nondecreasing", { timeout: 10_000 });
  await page.getByRole("button", { name: "P", exact: true }).click();
  const persistedSpecNodes = page.locator(".lineage-behavior_spec").filter({ hasText: "Monotonic regression requirement" });
  await expect(persistedSpecNodes).toHaveCount(2);
  await persistedSpecNodes.last().click({ force: true });
  await expect(page.getByTestId("behavior-spec")).toContainText("Monotonic");
  await expect(page.getByTestId("behavior-result")).toHaveCount(0);
  await page.getByRole("button", { name: "P", exact: true }).click();
  const comparisonNode = page.locator(".lineage-behavior_revision_comparison").first();
  await expect(comparisonNode).toBeVisible();
  await comparisonNode.click({ force: true });
  await expect(page.getByTestId("behavior-revision-comparison")).toContainText("PASS TO PASS");
  await expect(page.getByTestId("behavior-revision-comparison")).toContainText(`Baseline ${baselineResultId.slice(0, 12)} · candidate ${candidateResultId.slice(0, 12)}`);
});
