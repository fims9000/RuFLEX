import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(): string {
  return join(tmpdir(), `ruflex-train-evaluate-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function trainingCsv(): string {
  const rows = ["temperature,torque,target"];
  for (let index = 0; index < 36; index += 1) {
    const temperature = 10 + index * 0.7;
    const torque = 20 + (index * 11) % 60;
    const target = temperature + torque > 60 ? 1 : 0;
    rows.push(`${temperature.toFixed(2)},${torque.toFixed(2)},${target}`);
  }
  return `${rows.join("\n")}\n`;
}

test("Studio freezes selected TRAIN-only scaling in a run and restores it after reopen", async ({ page }) => {
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Scaling selection");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByLabel("Training normalization").selectOption("minmax");
  await expect(page.locator(".compact-definition")).toContainText("min–max scaling");
  const trainingResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/training/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  const trained = await trainingResponse;
  expect(trained.status()).toBe(201);
  expect(trained.request().postDataJSON().normalization).toBe("minmax");
  expect((await trained.json()).normalization.mode).toBe("minmax");
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted");
  await expect(page.getByText("This estimator does not provide measured epoch-wise history; validation metrics remain available.")).toBeVisible();
  await expect(page.getByText("Training trajectory · epoch 0 included", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.getByLabel("Training normalization")).toHaveValue("minmax");
  await expect(page.locator(".compact-definition").filter({ has: page.getByText("Saved run scaling", { exact: true }) })).toContainText("Saved run scalingminmax");
  await expect(page.getByText("This estimator does not provide measured epoch-wise history; validation metrics remain available.")).toBeVisible();
});

test("Studio offers the declared linear regression kind for a regression dataset", async ({ page }) => {
  const path = projectPath();
  const rows = ["x,y,target"];
  for (let index = 0; index < 36; index += 1) rows.push(`${index},${index % 7},${index * 2 + (index % 7)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Regression kind contract");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(rows.join("\n"));
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByLabel("Task").selectOption("regression");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.getByRole("option", { name: "Logistic / Linear Regression" })).toHaveAttribute("value", "linear_regression");
  await page.getByLabel("Training model").selectOption("linear_regression");
  const trainingResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/training/run") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  const trained = await trainingResponse;
  expect(trained.status()).toBe(201);
  expect(trained.request().postDataJSON().model_kind).toBe("linear_regression");
  expect((await trained.json()).model_kind).toBe("linear_regression");
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted");
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Residual evidence" })).toBeVisible();
  await expect(page.locator(".metric-card").filter({ has: page.getByText("rmse", { exact: true }) }).first().locator("strong")).toHaveText(/e-\d+/);
  const validationResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/analyses/evaluations") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Save validation evidence", exact: true }).click();
  const validation = await validationResponse;
  expect(validation.status()).toBe(201);
  const savedEvaluationId = (await validation.json()).evaluation_id;
  await expect(page.getByRole("heading", { name: "Validation prediction evidence" })).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  const reopenResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/open") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  const reopenedSessionId = (await (await reopenResponse).json()).session_id;
  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.getByLabel("Training model")).toHaveValue("linear_regression");
  await expect(page.locator(".run-provenance")).toContainText("native_linear@1");
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Residual evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validation prediction evidence" })).toBeVisible();
  const reopenedEvaluation = await page.request.get(`http://127.0.0.1:8010/api/projects/${reopenedSessionId}/analyses/evaluations/latest`);
  expect(reopenedEvaluation.status()).toBe(200);
  expect((await reopenedEvaluation.json()).evaluation_id).toBe(savedEvaluationId);
  await expect(page.getByRole("heading", { name: "Final test remains closed" })).toBeVisible();
  await page.getByText(/I confirm this policy was frozen before final-test access/).click();
  const finalResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/analyses/final-test") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Evaluate frozen final test", exact: true }).click();
  const finalEvaluation = await finalResponse;
  expect(finalEvaluation.status()).toBe(201);
  expect((await finalEvaluation.json()).evaluation_id).toBe(savedEvaluationId);
  await expect(page.getByRole("heading", { name: "Final-test evidence persisted separately" })).toBeVisible();
  await expect(page.locator(".final-test-gate .metric-card").filter({ has: page.getByText("rmse", { exact: true }) }).locator("strong")).toHaveText(/e-\d+/);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Final-test evidence persisted separately" })).toBeVisible();
});

test("a near-exact regression Study remains visible through its metric chart and reopen", async ({ page }) => {
  const path = projectPath();
  const rows = ["x,y,target"];
  for (let index = 0; index < 36; index += 1) rows.push(`${index},${index % 7},${index * 2 + (index % 7)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Regression Study chart");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(rows.join("\n"));
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByLabel("Task").selectOption("regression");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByRole("button", { name: "Freeze RANDOM SplitContract", exact: true }).click();
  await expect(page.getByRole("button", { name: "SplitContract frozen", exact: true })).toBeVisible();
  await page.getByLabel("Training model").selectOption("linear_regression");
  await page.getByLabel("Study seeds").fill("1, 2, 3");
  const submission = page.waitForResponse((response) => response.url().endsWith("/api/projects/training/study-jobs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  const response = await submission;
  expect(response.status()).toBe(202);
  expect(response.request().postDataJSON()).toMatchObject({ model_kind: "linear_regression", selection_metric: "rmse", seeds: [1, 2, 3] });
  await expect(page.getByText("Validation rmse across seeds", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Mean", { exact: true }).locator("..").locator("strong")).toHaveText(/e-\d+/);
  await expect(page.getByRole("button", { name: /SeedRun split 42 · train 3/ })).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  const reopenedResponse = page.waitForResponse((item) => item.url().endsWith("/api/projects/open") && item.request().method() === "POST");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  const sessionId = (await (await reopenedResponse).json()).session_id;
  await page.getByRole("button", { name: /Study .*3 seed runs/ }).click();
  await expect(page.getByText("Validation rmse across seeds", { exact: true })).toBeVisible();
  const reopenedStudy = await page.request.get(`http://127.0.0.1:8010/api/projects/${sessionId}/training/studies/latest`);
  expect(reopenedStudy.status()).toBe(200);
  const study = await reopenedStudy.json() as { selection_metric: string; selected_run_id: string; seed_runs: Array<{ training_seed: number; run_id: string; validation_metrics: { rmse: number } }> };
  expect(study.selection_metric).toBe("rmse");
  expect(study.seed_runs.map((run) => run.training_seed).sort()).toEqual([1, 2, 3]);
  const selected = [...study.seed_runs].sort((left, right) => left.validation_metrics.rmse - right.validation_metrics.rmse || left.training_seed - right.training_seed)[0];
  expect(study.selected_run_id).toBe(selected.run_id);
});

test("a rejected GROUP split can be corrected without uncertain-write recovery", async ({ page }) => {
  const path = projectPath();
  const rows = ["group,x,target", "a,1,0", "a,2,1", "a,3,0", "b,4,1", "b,5,0", "b,6,1"];
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Invalid split recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(rows.join("\n"));
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();

  await page.getByLabel("Split family").selectOption("GROUP");
  await page.getByLabel("Split identity column").selectOption("group");
  let releaseGroupSplit!: () => void;
  let markGroupSplitStarted!: () => void;
  const groupSplitGate = new Promise<void>((resolve) => { releaseGroupSplit = resolve; });
  const groupSplitStarted = new Promise<void>((resolve) => { markGroupSplitStarted = resolve; });
  let splitRequests = 0;
  await page.route("**/api/projects/dataset/splits", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    splitRequests += 1;
    if (splitRequests === 1) {
      markGroupSplitStarted();
      await groupSplitGate;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Freeze GROUP SplitContract", exact: true }).click();
  await groupSplitStarted;
  try {
    await expect(page.getByRole("button", { name: "Freezing split…", exact: true })).toBeDisabled();
    await expect(page.locator(".feature-toolbar")).toContainText("Saving split contract");
    await expect(page.locator('[data-ruflex-action="training.run"]')).toBeDisabled();
    expect(splitRequests).toBe(1);
  } finally {
    releaseGroupSplit();
  }
  await expect(page.getByRole("alert")).toContainText("GROUP split requires at least three distinct groups");
  await expect(page.getByTestId("split-contract-recovery")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Run multi-seed study", exact: true })).toBeDisabled();

  await page.getByLabel("Split family").selectOption("RANDOM");
  await page.getByRole("button", { name: "Freeze RANDOM SplitContract", exact: true }).click();
  const frozenSplitLabel = page.locator(".compact-definition dt").filter({ hasText: "Frozen split" });
  await expect(frozenSplitLabel.locator("xpath=following-sibling::dd[1]")).toContainText("RANDOM");
  await expect(page.getByTestId("split-contract-recovery")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeEnabled();
});

test("PRODUCT-02 performs real neuro-fuzzy training, validation evaluation and reopen", async ({ page }) => {
  test.setTimeout(45_000);
  const path = projectPath();

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Training route");
  await page.getByRole("button", { name: "Create project", exact: true }).click();

  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 36/)).toBeVisible();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText("Stored dataset preview", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.getByText("REAL TRAINING ENGINE", { exact: true })).toBeVisible();
  let splitContractPostCount = 0;
  await page.route("**/api/projects/dataset/splits", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    splitContractPostCount += 1;
    await route.fetch();
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "SplitContract response lost after persistence" }) });
  });
  await page.getByRole("button", { name: "Freeze RANDOM SplitContract", exact: true }).click();
  await expect(page.getByTestId("split-contract-recovery")).toContainText("SplitContract response lost after persistence");
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry exact SplitContract lookup", exact: true }).click();
  await expect(page.getByTestId("split-contract-recovery")).toHaveCount(0);
  expect(splitContractPostCount).toBe(1);
  await expect(page.getByLabel("Training model").locator("option")).toHaveCount(5);
  await page.getByLabel("Training model").selectOption("decision_tree");
  await expect(page.getByLabel("Maximum depth")).toBeVisible();
  await expect(page.getByLabel("Epochs")).toHaveCount(0);
  await page.getByLabel("Training model").selectOption("flat_neuro_fuzzy");
  await expect(page.getByLabel("Epochs")).toBeVisible();
  await expect(page.getByLabel("Maximum depth")).toHaveCount(0);
  await expect(page.getByLabel("Trees / estimators")).toHaveCount(0);
  await page.getByLabel("Epochs").fill("2");
  await page.getByLabel("Batch size").fill("16");
  let transformReads = 0;
  await page.route("**/api/projects/*/dataset/transforms/*", async (route) => {
    transformReads += 1;
    if (transformReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved transform temporarily unavailable" }) });
    }
    return route.continue();
  });
  let trainingPostCount = 0;
  let trainingRequestBody: Record<string, unknown> | null = null;
  let releaseTrainingRequest!: () => void;
  let markTrainingRequestStarted!: () => void;
  const trainingRequestGate = new Promise<void>((resolve) => { releaseTrainingRequest = resolve; });
  const trainingRequestStarted = new Promise<void>((resolve) => { markTrainingRequestStarted = resolve; });
  await page.route("**/api/projects/training/run", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    trainingPostCount += 1;
    trainingRequestBody = route.request().postDataJSON() as Record<string, unknown>;
    markTrainingRequestStarted();
    await trainingRequestGate;
    await route.fetch();
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "TrainingRun response lost after persistence" }) });
  });
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await trainingRequestStarted;
  try {
    await expect(page.locator('[data-ruflex-action="training.run"]')).toBeDisabled();
    await expect(page.getByLabel("Training model")).toBeDisabled();
    expect(trainingPostCount).toBe(1);
  } finally {
    releaseTrainingRequest();
  }

  const trainingRecovery = page.getByTestId("training-run-recovery");
  await expect(trainingRecovery).toContainText("TrainingRun response lost after persistence");
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry exact TrainingRun lookup", exact: true }).click();
  await expect(trainingRecovery).toHaveCount(0);
  expect(trainingPostCount).toBe(1);
  expect(trainingRequestBody?.model_kind).toBe("flat_neuro_fuzzy");

  const runEvidence = page.locator(".run-provenance");
  await expect(runEvidence).toBeVisible({ timeout: 30_000 });
  await expect(runEvidence).toContainText("model artifact persisted");
  await expect(runEvidence).toContainText("train-only preprocessing persisted");
  await page.getByText("Data governance evidence", { exact: true }).click();
  const governanceError = page.getByRole("alert").filter({ hasText: "saved transform temporarily unavailable" });
  await expect(governanceError).toBeVisible();
  await governanceError.getByRole("button", { name: "Retry data evidence", exact: true }).click();
  await expect(page.getByText(/RANDOM · seed 42/)).toBeVisible();
  await expect(page.getByText(/Train \d+ · validation \d+ · locked test \d+/)).toBeVisible();
  await expect(page.getByText("TRAIN only · 2 persisted step(s)")).toBeVisible();
  expect(transformReads).toBe(2);
  await expect(page.getByText("No structural leakage findings were recorded by this audit.", { exact: true })).toBeVisible();
  await expect(page.locator(".run-summary-strip")).toBeVisible();
  await expect(page.getByText("Training trajectory · epoch 0 included", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("VALIDATION EVIDENCE", { exact: true })).toBeVisible();
  const evaluationFooter = page.locator(".evaluation-footer");
  await expect(evaluationFooter).toBeVisible();
  await expect(evaluationFooter).toContainText("test rows remain locked");
  await expect(page.getByRole("heading", { name: "Validation prediction evidence", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save validation evidence", exact: true }).click();
  await expect(page.getByText("Validation ROC curve · raw model", { exact: true })).toBeVisible();
  await expect(page.getByText("Validation precision–recall curve · raw model", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Select F1 threshold \(raw\)/ }).click();
  await expect(page.getByRole("heading", { name: /Frozen policy threshold/ })).toBeVisible();
  await page.getByLabel("Selective confidence cutoff").fill("0.80");
  await page.getByRole("button", { name: "Save ACCEPT / REVIEW policy", exact: true }).click();
  await expect(page.getByText("REVIEW BELOW 0.80", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "P", exact: true }).click();
  const auditNode = page.locator(".lineage-node.lineage-leakage_audit").filter({ hasText: "Data leakage audit" }).first();
  await expect(auditNode).toBeVisible();
  await auditNode.click();
  await expect(page.getByRole("region", { name: "Selected data provenance object" })).toContainText("CONFIRMATORY");
  await expect(page.getByText("No structural findings were recorded.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "P", exact: true }).click();
  const splitNode = page.locator(".lineage-node.lineage-split_contract").first();
  await expect(splitNode).toBeVisible();
  await splitNode.click();
  await expect(page.getByRole("region", { name: "Selected data provenance object" })).toContainText("Locked test");
  await page.getByRole("button", { name: /Training run/ }).click();
  await expect(page.locator(".run-provenance")).toBeVisible();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted");
  await expect(page.locator(".run-provenance")).toContainText("train-only preprocessing persisted");
  await page.getByText("Data governance evidence", { exact: true }).click();
  await expect(page.getByText(/RANDOM · seed 42/)).toBeVisible();
  await expect(page.getByText("TRAIN only · 2 persisted step(s)")).toBeVisible();
  await page.getByRole("button", { name: "A", exact: true }).click();
  await expect(page.getByText("VALIDATION EVIDENCE", { exact: true })).toBeVisible();
  await expect(page.getByText("Validation ROC curve · raw model", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Frozen policy threshold/ })).toBeVisible();
  await expect(page.getByText("REVIEW BELOW 0.80", { exact: false })).toBeVisible();

  const reopened = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  expect(reopened.status()).toBe(200);
  const { session_id: reopenedSessionId } = await reopened.json();
  const unopenedFinalTest = await page.request.get(`http://127.0.0.1:8010/api/projects/${reopenedSessionId}/analyses/final-test/latest`);
  expect(unopenedFinalTest.status()).toBe(404);
});

test("PRODUCT-02b retries a persisted decision-tree capability check without claiming unsupported", async ({ page }) => {
  test.setTimeout(45_000);
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Tree capability retry");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  let backendCatalogReads = 0;
  await page.route("**/api/runtime/backends", async (route) => {
    backendCatalogReads += 1;
    if (backendCatalogReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "execution backend catalog temporarily unavailable" }) });
    }
    return route.continue();
  });
  await page.getByRole("button", { name: "S", exact: true }).click();
  const backendCatalogError = page.getByTestId("execution-backend-catalog-error");
  await expect(backendCatalogError).toContainText("execution backend catalog temporarily unavailable");
  await expect(page.getByRole("button", { name: "Run multi-seed study", exact: true })).toBeDisabled();
  await backendCatalogError.getByRole("button", { name: "Retry backend check" }).click();
  await expect(backendCatalogError).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run multi-seed study", exact: true })).toBeEnabled();
  expect(backendCatalogReads).toBe(2);
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByLabel("Training normalization").selectOption("minmax");
  let capabilityReads = 0;
  let treePathReads = 0;
  await page.route("**/training/runs/*/capabilities", async (route) => {
    capabilityReads += 1;
    if (capabilityReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "run capability store temporarily unavailable" }) });
    }
    return route.continue();
  });
  await page.route("**/evidence/tree-path/latest", async (route) => {
    treePathReads += 1;
    if (treePathReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "tree path evidence temporarily unavailable" }) });
    }
    return route.continue();
  });
  let artifactRefreshReads = 0;
  await page.route("**/api/projects/*/artifacts", async (route) => {
    artifactRefreshReads += 1;
    if (artifactRefreshReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "post-training artifact inventory temporarily unavailable" }) });
    }
    return route.continue();
  });
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toBeVisible({ timeout: 30_000 });
  const artifactRefreshError = page.getByTestId("artifact-hydration-error");
  await expect(artifactRefreshError).toContainText("post-training artifact inventory temporarily unavailable");
  await artifactRefreshError.getByRole("button", { name: "Retry artifact list" }).click();
  await expect(artifactRefreshError).toHaveCount(0);
  expect(artifactRefreshReads).toBe(2);
  const error = page.getByRole("alert").filter({ hasText: "Could not verify saved run capabilities" });
  await expect(error).toContainText("run capability store temporarily unavailable");
  await expect(page.getByRole("button", { name: "Trace exact tree path", exact: true })).toHaveCount(0);
  await error.getByRole("button", { name: "Retry run capability check", exact: true }).click();
  await expect(page.getByRole("button", { name: "Trace exact tree path", exact: true })).toBeVisible();
  expect(capabilityReads).toBe(2);
  const treeError = page.getByRole("alert").filter({ hasText: "tree path evidence temporarily unavailable" });
  await expect(treeError).toBeVisible();
  await treeError.getByRole("button", { name: "Retry tree-path check", exact: true }).click();
  await expect(page.getByText("No saved tree-path evidence exists yet for this project.", { exact: true })).toBeVisible();
  expect(treePathReads).toBe(2);
  let treePathPosts = 0;
  await page.route("**/api/projects/training/tree-path", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    treePathPosts += 1;
    await route.fetch();
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "TreePathEvidence response lost after persistence" }) });
  });
  const treeInputs = page.locator('input[aria-label^="Tree input "]');
  await treeInputs.first().fill("");
  await expect(page.getByText(/a blank field is not zero/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Trace exact tree path", exact: true })).toBeDisabled();
  expect(treePathPosts).toBe(0);
  for (let index = 0; index < await treeInputs.count(); index += 1) await treeInputs.nth(index).fill("12");
  await expect(page.getByRole("button", { name: "Trace exact tree path", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Trace exact tree path", exact: true }).click();
  await expect(page.getByTestId("tree-path-recovery")).toContainText("TreePathEvidence response lost after persistence");
  await page.getByRole("button", { name: "Retry exact tree-path lookup", exact: true }).click();
  await expect(page.getByTestId("tree-path-recovery")).toHaveCount(0);
  expect(treePathPosts).toBe(1);
  await expect(page.locator(".tree-path-panel .info-message strong")).toContainText("EXACT TREE EXECUTION PATH");

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "P", exact: true }).click();
  const treeNode = page.locator(".lineage-node.lineage-tree_path").first();
  const runNode = page.locator(".lineage-node.lineage-training_run").first();
  await expect(treeNode).toBeVisible();
  await expect(runNode).toBeVisible();
  let releaseTreeRead!: () => void;
  let markTreeReadStarted!: () => void;
  const treeReadGate = new Promise<void>((resolve) => { releaseTreeRead = resolve; });
  const treeReadStarted = new Promise<void>((resolve) => { markTreeReadStarted = resolve; });
  await page.route("**/api/projects/*/evidence/tree-path/*", async (route) => {
    markTreeReadStarted();
    await treeReadGate;
    await route.continue();
  });
  try {
    await treeNode.click();
    await treeReadStarted;
    await runNode.click();
    await expect(page.locator(".workspace-header .eyebrow")).toHaveText("STUDIES");
  } finally {
    releaseTreeRead();
  }
  await expect(page.locator(".workspace-header .eyebrow")).toHaveText("STUDIES");
});

test("Studio traces a categorical tree sample through frozen ordinal codes and reopens it", async ({ page }) => {
  const path = projectPath();
  const rows = ["temperature,material,target"];
  for (let index = 0; index < 48; index += 1) {
    const material = index % 2 ? "steel" : "brass";
    rows.push(`${10 + index},${material},${index > 23 || material === "steel" ? 1 : 0}`);
  }
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Categorical tree path");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(rows.join("\n"));
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByLabel("Training normalization").selectOption("minmax");
  let transformReads = 0;
  await page.route("**/api/projects/*/dataset/transforms/*", async (route) => {
    transformReads += 1;
    if (transformReads === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "frozen encoder temporarily unavailable" }) });
    return route.continue();
  });
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toBeVisible();
  await expect(page.getByText(/Resolve this run's frozen categorical encoding/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Trace exact tree path", exact: true })).toBeDisabled();
  await page.getByText("Data governance evidence", { exact: true }).click();
  await page.getByRole("button", { name: "Retry data evidence", exact: true }).click();
  const categoryInput = page.locator('select[aria-label="Tree input material"]');
  await expect(categoryInput).toBeVisible();
  await expect(categoryInput.locator("option")).toHaveText(["brass · frozen code 0", "steel · frozen code 1"]);
  await categoryInput.selectOption("1");
  await page.getByLabel("Tree input temperature").fill("28");
  const traceResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/training/tree-path") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Trace exact tree path", exact: true }).click();
  const trace = await traceResponse;
  expect(trace.status()).toBe(201);
  expect(trace.request().postDataJSON().sample).toMatchObject({ temperature: 28, material: 1 });
  const evidenceId = (await trace.json()).evidence_id;
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  const reopenResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/open") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  const reopened = await (await reopenResponse).json();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await expect(page.locator(".tree-path-panel .info-message strong")).toContainText("EXACT TREE EXECUTION PATH");
  const persisted = await page.request.get(`http://127.0.0.1:8010/api/projects/${reopened.session_id}/evidence/tree-path/latest`);
  expect(persisted.status()).toBe(200);
  expect((await persisted.json()).evidence_id).toBe(evidenceId);
});

test("PRODUCT-02 blocks validation policy changes when final-test access status is unavailable", async ({ page }) => {
  test.setTimeout(45_000);
  let boundaryRequests = 0;
  let evaluationRequests = 0;
  let selectivePolicyRequests = 0;
  await page.route("**/api/projects/*/analyses/final-test/latest", async (route) => {
    boundaryRequests += 1;
    if (boundaryRequests === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "final-test boundary store unavailable" }) });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No final-test evaluation exists in this project." }) });
  });
  await page.route("**/api/projects/*/analyses/evaluations/latest", async (route) => {
    evaluationRequests += 1;
    if (evaluationRequests === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved evaluation store unavailable" }) });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No saved evaluation exists in this project." }) });
  });
  await page.route("**/api/projects/*/analyses/selective-policies/latest", async (route) => {
    selectivePolicyRequests += 1;
    if (selectivePolicyRequests === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved policy store unavailable" }) });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No selective policy exists in this project." }) });
  });
  const path = projectPath();
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Final-test boundary recovery");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(trainingCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByRole("button", { name: "Freeze RANDOM SplitContract", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "A", exact: true }).click();

  await expect(page.getByText("Could not verify saved validation Evaluation", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save validation evidence" })).toBeDisabled();
  await page.getByRole("button", { name: "Retry validation evidence check" }).click();
  await expect(page.getByRole("button", { name: "Save validation evidence" })).toBeEnabled();
  expect(evaluationRequests).toBe(2);
  await expect(page.getByRole("heading", { name: "Final-test state unavailable" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "final-test boundary store unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Select F1 threshold (raw)" })).toBeDisabled();
  await expect(page.getByRole("alert").filter({ hasText: "saved policy store unavailable" })).toBeVisible();
  await page.getByRole("button", { name: "Retry saved policy check" }).click();
  await expect(page.getByRole("button", { name: "Select F1 threshold (raw)" })).toBeDisabled();
  expect(selectivePolicyRequests).toBe(2);
  await page.getByRole("button", { name: "Retry final-test status check" }).click();
  await expect(page.getByRole("heading", { name: "Final test remains closed" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Select F1 threshold (raw)" })).toBeEnabled();
  expect(boundaryRequests).toBe(2);
});
