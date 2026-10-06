import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const productScreenshots = resolve(import.meta.dirname, "../../docs/product/screenshots");
const productRuntimeEvidence = resolve(import.meta.dirname, "../../docs/product/PRODUCT_V1_EVIDENCE_RUNTIME.json");
const updateProductEvidence = process.env.RUFLEX_UPDATE_PRODUCT_EVIDENCE === "1";

function projectPath(): string {
  return join(tmpdir(), `ruflex-product-evidence-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

function telemetryCsv(): string {
  const rows = ["device_id,temperature,torque,target"];
  for (let index = 0; index < 80; index += 1) {
    const temperature = 8 + index * 0.55;
    const torque = 12 + (index * 13) % 75;
    rows.push(`device-${index % 4},${temperature.toFixed(2)},${torque.toFixed(2)},${temperature + torque > 64 ? 1 : 0}`);
  }
  return `${rows.join("\n")}\n`;
}

async function capture(page: import("@playwright/test").Page, directory: string, filename: string, anchor?: import("@playwright/test").Locator) {
  if (anchor) await anchor.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(directory, filename) });
}

/**
 * This is not a fixture gallery. It creates one canonical persisted project,
 * drives the React Studio. Product-doc screenshots are replaced only in the
 * explicit capture mode; ordinary E2E runs write their proof to test output.
 */
test("PRODUCT-EVIDENCE captures the frozen V1 Studio route from persisted objects", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  page.setDefaultTimeout(15_000);
  const screenshots = updateProductEvidence ? productScreenshots : testInfo.outputPath("product-evidence");
  const runtimeEvidence = updateProductEvidence ? productRuntimeEvidence : join(screenshots, "PRODUCT_V1_EVIDENCE_RUNTIME.json");
  await mkdir(screenshots, { recursive: true });
  const path = projectPath();
  const ids: Record<string, unknown> = { project_path: "ephemeral local product-evidence project", object_types: [] };

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Product V1 evidence demonstration");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.locator(".project-object-tree")).toBeVisible();

  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill(telemetryCsv());
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 80 · columns: 4/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(/Contract: target · binary_classification/)).toBeVisible();
  await capture(page, screenshots, "01_project_explorer.png");
  await capture(page, screenshots, "02_dataset_contract.png", page.getByText(/Contract: target · binary_classification/));

  // Declare scope before any test access. It remains an operational declaration,
  // not evidence of generalization outside the stated support.
  await page.getByLabel("Intended use").fill("Equipment health decision support with human review");
  await page.getByLabel("Novelty axis").selectOption("device");
  await page.getByLabel("Generalization scope field").selectOption("temperature");
  await page.getByLabel("Supported values").fill("10, 20, 30");
  await page.getByLabel("Forbidden values").fill("999");
  await page.getByLabel("Candidate value to classify").fill("999");
  await page.getByRole("button", { name: "Declare generalization contract", exact: true }).click();
  await page.getByRole("button", { name: "Freeze evaluation contract", exact: true }).click();
  await page.getByRole("button", { name: "Check candidate scope", exact: true }).click();
  await expect(page.getByText(/Outside supported scope: BLOCK/)).toBeVisible();

  await page.getByRole("button", { name: "New FIS from dataset" }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();
  await expect(page.getByText("CANONICAL FUZZY DESIGNER", { exact: true })).toBeVisible();
  await capture(page, screenshots, "03_fis_designer.png");
  await page.getByLabel("FIS family").selectOption("sugeno");
  await page.getByRole("button", { name: "Save FIS", exact: true }).click();
  await page.getByRole("button", { name: "Run exact inference", exact: true }).click();
  await expect(page.getByText("OUTPUT", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open exact trace", exact: true }).click();
  await expect(page.getByText("E4 · EXACT COMPUTATIONAL TRACE", { exact: true })).toBeVisible();
  await capture(page, screenshots, "04_exact_fis_trace.png");

  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByLabel("Study seeds").fill("7, 8, 9");
  await page.getByRole("button", { name: "Run multi-seed study", exact: true }).click();
  await expect(page.getByText("Validation f1 across seeds", { exact: true })).toBeVisible({ timeout: 45_000 });
  await capture(page, screenshots, "05_training_and_study.png", page.getByText("Validation f1 across seeds", { exact: true }));

  // Restore a real logistic run as active evidence subject after the Study.
  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("logistic_regression");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByRole("button", { name: "A", exact: true }).click();
  await page.getByRole("button", { name: "Save validation evidence", exact: true }).click();
  const calibrationButton = page.getByRole("button", { name: "Fit validation calibration", exact: true });
  await calibrationButton.click();
  await expect(page.getByRole("button", { name: "Refit calibration", exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Brier calibrated", { exact: true })).toBeVisible();
  await capture(page, screenshots, "06_evaluation_and_calibration.png", page.getByText("Brier calibrated", { exact: true }));
  await page.getByRole("button", { name: "Select F1 threshold (calibrated)", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Probability → calibration → threshold → class", exact: true })).toBeVisible();
  await capture(page, screenshots, "07_decision_threshold.png", page.getByRole("heading", { name: "Probability → calibration → threshold → class", exact: true }));
  await page.getByLabel("Selective confidence cutoff").fill("0.80");
  await page.getByRole("button", { name: "Save ACCEPT / REVIEW policy", exact: true }).click();
  await expect(page.getByText("REVIEW BELOW 0.80", { exact: false })).toBeVisible();
  await capture(page, screenshots, "12_selective_review_policy.png", page.getByText("REVIEW BELOW 0.80", { exact: false }));
  await page.getByText(/I confirm this policy was frozen before final-test access/).click();
  await page.getByRole("button", { name: "Evaluate frozen final test", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Final-test evidence persisted separately", exact: true })).toBeVisible();
  await page.getByLabel("Slice minimum").fill("10");
  await page.getByLabel("Slice maximum").fill("30");
  await page.getByRole("button", { name: "Run and persist slice", exact: true }).click();
  await expect(page.getByText(/Scope classifications use GeneralizationContract/)).toBeVisible();
  await capture(page, screenshots, "08_generalization_and_slices.png", page.getByText(/Scope classifications use GeneralizationContract/));

  await page.getByRole("button", { name: "E", exact: true }).click();
  await page.getByRole("button", { name: "Generate explanation", exact: true }).click();
  await page.getByRole("button", { name: "Run explanation checks", exact: true }).click();
  await expect(page.getByText("PASSED_AVAILABLE_CHECKS", { exact: true })).toBeVisible();
  await capture(page, screenshots, "09_xai_and_explanation_check.png", page.getByText("PASSED_AVAILABLE_CHECKS", { exact: true }));
  // Two equivalent declared cases for the first independently trained run.
  await page.getByLabel("temperature").fill("30");
  await page.getByRole("button", { name: "Generate explanation", exact: true }).click();

  await page.getByRole("button", { name: "S", exact: true }).click();
  await page.getByLabel("Training model").selectOption("decision_tree");
  await page.getByRole("button", { name: "Run real training", exact: true }).click();
  await expect(page.locator(".run-provenance")).toContainText("model artifact persisted", { timeout: 30_000 });
  await page.getByRole("button", { name: "E", exact: true }).click();
  await page.getByRole("button", { name: "Generate explanation", exact: true }).click();
  await page.getByLabel("temperature").fill("30");
  await page.getByRole("button", { name: "Generate explanation", exact: true }).click();
  const explanationChoices = page.locator('.comparison-choice input[type="checkbox"]');
  await expect(explanationChoices).toHaveCount(4);
  for (let index = 0; index < 4; index += 1) await explanationChoices.nth(index).check();
  await page.getByRole("button", { name: "Compare explanation reproducibility", exact: true }).click();
  await expect(page.getByTestId("reproducibility-result")).toContainText("EXPLANATION AGREEMENT");
  await capture(page, screenshots, "10_cross_run_reproducibility.png", page.getByTestId("reproducibility-result"));

  await page.getByRole("button", { name: "Create and run BehaviorSpec", exact: true }).click();
  await expect(page.getByTestId("behavior-result")).toBeVisible();
  await capture(page, screenshots, "11_behavior_specs.png", page.getByTestId("behavior-result"));
  await page.getByRole("button", { name: "Enumerate exact Decision Tree paths", exact: true }).click();
  await expect(page.getByTestId("exhaustive-result")).toContainText("EXACT_FINITE_STRUCTURE");
  await capture(page, screenshots, "13_exhaustive_lab.png", page.getByTestId("exhaustive-result"));

  // The FIS is a persisted model revision. Open its actual workbench and run
  // the train-only expert correction; no final-test rows are used by this action.
  await page.getByRole("button", { name: /Risk FIS|FIS/ }).first().click();
  await expect(page.getByText("EXPERT CORRECTION", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refit unlocked consequents on TRAIN", exact: true }).click();
  await expect(page.getByText(/Last correction:/)).toBeVisible({ timeout: 20_000 });
  await capture(page, screenshots, "14_expert_correction.png");

  await page.getByRole("button", { name: "E", exact: true }).click();
  await page.getByRole("button", { name: "Build AssuranceCase", exact: true }).click();
  await expect(page.getByTestId("assurance-case")).toBeVisible();
  await capture(page, screenshots, "16_assurance_case.png", page.getByTestId("assurance-case"));
  await page.getByRole("button", { name: "Export and validate bundle", exact: true }).click();
  await expect(page.getByTestId("verification-bundle")).toBeVisible();
  await expect(page.getByTestId("verification-bundle")).toContainText("Portable validation");
  await expect(page.getByTestId("verification-bundle")).toContainText("PASS");
  await capture(page, screenshots, "17_verification_bundle.png", page.getByTestId("verification-bundle"));
  await page.getByRole("button", { name: "Run telemetry demonstration", exact: true }).click();
  await expect(page.getByTestId("condition-monitoring-demo")).toBeVisible();
  await capture(page, screenshots, "18_condition_monitoring_demo.png", page.getByTestId("condition-monitoring-demo"));

  // Add one FIS-bound BehaviorSpec through the real API boundary. The Studio
  // has already created run-bound BehaviorSpecs above; this explicit binding
  // proves the RC2.1 FIS revision lineage edge after the following reopen.
  const lineageSessionResponse = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  expect(lineageSessionResponse.ok()).toBeTruthy();
  const lineageSession = await lineageSessionResponse.json() as { session_id: string };
  const activeFisResponse = await page.request.get(`http://127.0.0.1:8010/api/projects/${lineageSession.session_id}/fis/active`);
  expect(activeFisResponse.ok()).toBeTruthy();
  const activeFis = await activeFisResponse.json() as { fis_id: string; semantic_hash: string; inputs: Array<{ name: string; minimum: number; maximum: number }> };
  const fisSample = Object.fromEntries(activeFis.inputs.map((input) => [input.name, (input.minimum + input.maximum) / 2]));
  const fisSpecResponse = await page.request.post("http://127.0.0.1:8010/api/projects/evidence/behavior-specs", { data: {
    session_id: lineageSession.session_id, fis_id: activeFis.fis_id, fis_semantic_hash: activeFis.semantic_hash,
    name: "FIS revision range evidence", kind: "output_range", sample: fisSample, comparison_sample: null,
    minimum: 0, maximum: 1, expected_direction: null, tolerance: 1e-9,
    rationale: "Evidence capture: exact FIS revision behavior requirement.",
  } });
  expect(fisSpecResponse.ok()).toBeTruthy();
  const fisSpec = await fisSpecResponse.json() as { spec_id: string };
  const fisResultResponse = await page.request.post("http://127.0.0.1:8010/api/projects/evidence/behavior-specs/run", { data: { session_id: lineageSession.session_id, spec_id: fisSpec.spec_id } });
  expect(fisResultResponse.ok()).toBeTruthy();
  await fisResultResponse.json() as { result_id: string };
  // Runtime IDs are visible in the screenshots as evidence of a real route,
  // but must not make the tracked documentation change on every normal QA run.
  ids.fis_revision = "runtime-generated persisted FIS revision";
  ids.fis_behavior_spec = "runtime-generated persisted BehaviorSpec";
  ids.fis_behavior_result = "runtime-generated persisted BehaviorSpecResult";

  let expertCorrectionReadFailed = false;
  await page.route(`**/api/projects/*/fis/expert-correction/latest`, async (route) => {
    if (!expertCorrectionReadFailed) {
      expertCorrectionReadFailed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary expert correction read failure" }) });
      return;
    }
    await route.continue();
  });
  let generalizationReadFailed = false;
  await page.route(`**/api/projects/*/generalization/contracts/active`, async (route) => {
    if (!generalizationReadFailed) {
      generalizationReadFailed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary GeneralizationContract read failure" }) });
      return;
    }
    await route.continue();
  });
  let latestAssuranceReadFailed = false;
  await page.route(`**/api/projects/*/evidence/assurance-cases/latest`, async (route) => {
    if (!latestAssuranceReadFailed) {
      latestAssuranceReadFailed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary AssuranceCase read failure" }) });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByTestId("evidence-generalization-hydration-error")).toContainText("Temporary GeneralizationContract read failure");
  await expect(page.getByRole("button", { name: "Run telemetry demonstration", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry GeneralizationContract", exact: true }).click();
  await expect(page.getByTestId("evidence-generalization-hydration-error")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run telemetry demonstration", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "M", exact: true }).click();
  await expect(page.getByTestId("expert-correction-load-error")).toContainText("Temporary expert correction read failure");
  await page.getByRole("button", { name: "Retry expert correction", exact: true }).click();
  await expect(page.getByText(/Last correction:/)).toBeVisible();
  // The Lineage screen is reached through the restored real project view.
  await page.getByRole("button", { name: "P", exact: true }).click();
  await expect(page.getByText("PROJECT LINEAGE", { exact: true })).toBeVisible();
  await capture(page, screenshots, "15_lineage.png", page.getByText("PROJECT LINEAGE", { exact: true }));
  let bundleReadFailed = false;
  await page.route(`**/api/projects/*/evidence/verification-bundles/*`, async (route) => {
    if (!bundleReadFailed) {
      bundleReadFailed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary VerificationBundle read failure" }) });
      return;
    }
    await route.continue();
  });
  // ReactFlow's fit-view geometry can place a node beyond the clipped canvas
  // after the persisted evidence graph grows; dispatch the node's real DOM
  // click rather than relying on viewport scrolling inside the clipped pane.
  await page.locator(".lineage-verification_bundle").first().evaluate((node) => node.dispatchEvent(new MouseEvent("click", { bubbles: true })));
  await expect(page.getByTestId("lineage-object-load-error")).toContainText("Temporary VerificationBundle read failure");
  await page.getByRole("button", { name: "Retry selected object", exact: true }).click();
  await expect(page.getByTestId("verification-bundle-record")).toBeVisible();
  await expect(page.getByText("Temporary VerificationBundle read failure", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "E", exact: true }).click();
  await expect(page.getByText("Temporary AssuranceCase read failure", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry AssuranceCase", exact: true }).click();
  await expect(page.getByTestId("assurance-case")).toBeVisible();
  await capture(page, screenshots, "19_close_reopen_restored.png", page.getByTestId("assurance-case"));

  // Persist capture provenance outside the product project. IDs are runtime
  // generated, while screenshots themselves show the shortened canonical IDs.
  const reopened = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path, read_only: true } });
  expect(reopened.ok()).toBeTruthy();
  await reopened.json();
  ids.reopen_session = "runtime-generated read-only reopen session";
  ids.object_types = ["DatasetContract", "FIS revision", "TrainingRun", "TrainingStudy", "Evaluation", "CalibrationTransform", "DecisionThresholdPolicy", "SelectivePredictionPolicy", "GeneralizationContract", "SliceAnalysis", "Explanation", "ExplanationCheck", "ExplanationReproducibilityAnalysis", "BehaviorSpec", "BehaviorSpecResult", "ExhaustiveLabResult", "ExpertCorrectionRevision", "FinalTestEvaluation", "AssuranceCase", "VerificationBundle"];
  await writeFile(runtimeEvidence, `${JSON.stringify(ids, null, 2)}\n`, "utf8");
});
