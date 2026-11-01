import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { openTrainingSettings } from "./helpers/trainingSettings";

const families = ["logistic_regression", "decision_tree", "random_forest", "gradient_boosting", "mlp", "flat_neuro_fuzzy"] as const;
const extraMethods: Record<string, string[]> = {
  logistic_regression: ["shap"], decision_tree: ["tree_shap"], random_forest: ["shap"],
  gradient_boosting: ["tree_shap"], mlp: ["shap"], flat_neuro_fuzzy: ["integrated_gradients", "gradient_shap"],
};
const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name });

function uploadedCsv(task: "regression" | "binary_classification"): string {
  const rows = ["sample_id,temperature,torque,mode,excluded_hint,target"];
  for (let index = 0; index < 96; index += 1) {
    const temperature = 10 + (index * 7) % 43;
    const torque = 20 + (index * 11) % 53;
    const mode = index % 3 === 0 ? "service" : "normal";
    const score = temperature * .4 + torque * .6 + (mode === "service" ? 2 : 0);
    rows.push(`sample-${index},${index % 13 === 0 ? "" : temperature},${torque},${mode},${index},${task === "regression" ? score.toFixed(3) : Number(score >= 38)}`);
  }
  return rows.join("\n");
}

async function capture(page: Page, testInfo: TestInfo, name: string) {
  await testInfo.attach(name, { body: await page.screenshot({ animations: "disabled" }), contentType: "image/png" });
  if (process.env.RUFLEX_CAPTURE_MODEL_SCREENSHOTS === "1") {
    const folder = resolve("..", "docs", "qa", "screenshots", "model-matrix");
    mkdirSync(folder, { recursive: true });
    await page.screenshot({ path: join(folder, `${name}.png`), animations: "disabled" });
  }
}

async function createProject(page: Page, path: string, practice: boolean) {
  await page.goto("/");
  await page.getByLabel("Папка проекта").fill(path);
  await page.getByLabel("Название проекта").fill("Проверка моделей на учебных данных");
  await page.getByLabel("Тип нового проекта").selectOption(practice ? "practice" : "empty");
  const response = page.waitForResponse((item) => item.url().endsWith("/api/projects") && item.request().method() === "POST");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  expect((await response).status()).toBe(201);
  return (await (await response).json()).session_id as string;
}

async function importUserCsv(page: Page, task: "regression" | "binary_classification") {
  await nav(page, "Данные").click();
  const inspected = page.waitForResponse((item) => item.url().endsWith("/api/projects/dataset/import/inspect") && item.request().method() === "POST");
  await page.getByLabel("Файл CSV или XLSX").setInputFiles({ name: "measurements.csv", mimeType: "text/csv", buffer: Buffer.from(uploadedCsv(task)) });
  expect((await inspected).status()).toBe(200);
  await page.getByLabel("Целевой столбец", { exact: true }).selectOption("target");
  await page.getByLabel("Задача", { exact: true }).selectOption(task);
  await page.getByLabel("Роль столбца sample_id").selectOption("id");
  await page.getByLabel("Роль столбца excluded_hint").selectOption("excluded");
  const imported = page.waitForResponse((item) => item.url().endsWith("/api/projects/dataset/import") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="dataset.import.confirm"]').click();
  expect((await imported).status()).toBe(200);
  const contract = (await (await imported).json()).contract;
  expect(contract.feature_columns).toEqual(["temperature", "torque", "mode"]);
  expect(contract.id_columns).toEqual(["sample_id"]);
  expect(contract.excluded_columns).toEqual(["excluded_hint"]);
  return contract;
}

test.describe("each catalog model has a real Russian user route", () => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Run the user matrix with VITE_RUFLEX_UI_LANG=ru");
  for (const task of ["binary_classification", "regression"] as const) {
    for (const family of families) {
      const model = task === "regression" && family === "logistic_regression" ? "linear_regression" : family;
      test(`${task} / ${model}: data → fit → validation → explanation → final test → reopen`, async ({ page }, testInfo) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width: 1280, height: 850 });
        const browserErrors: string[] = [];
        page.on("pageerror", (error) => browserErrors.push(error.message));
        const path = join(tmpdir(), `ruflex-model-matrix-${task}-${model}-${Date.now()}`);
        const sessionId = await createProject(page, path, task === "binary_classification");
        if (task === "regression") {
          await importUserCsv(page, task);
          await nav(page, "Обучение").click();
        }
        const selector = page.getByLabel("Модель для обучения");
        await expect(selector).toBeEnabled();
        await selector.selectOption(model);
        await expect(page.getByTestId("training-settings")).not.toHaveAttribute("open", "");
        if (family !== "logistic_regression" && family !== "decision_tree") await openTrainingSettings(page);
        if (family === "flat_neuro_fuzzy" || family === "mlp") await page.getByLabel("Эпохи", { exact: true }).fill("8");
        if (family === "flat_neuro_fuzzy") await page.getByLabel("Правил на слой").fill("4");
        if (family === "mlp") await page.getByLabel("Нейронов в скрытом слое").fill("8");
        if (family === "random_forest" || family === "gradient_boosting") await page.getByLabel("Число деревьев").fill("8");
        const fitted = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/run") && item.request().method() === "POST");
        await page.locator('[data-ruflex-action="training.run"]').click();
        const fitResponse = await fitted;
        expect(fitResponse.status(), await fitResponse.text()).toBe(201);
        const run = await fitResponse.json();
        expect(run.model_kind).toBe(model);
        expect(run.task).toBe(task);
        expect(run.split.test_status).toBe("LOCKED_NOT_EVALUATED");
        expect(run.validation_metrics[task === "regression" ? "rmse" : "f1"]).toEqual(expect.any(Number));
        await expect(page.getByTestId("trained-model-name")).toBeVisible();
        await expect(page.locator('[data-ruflex-action="training.run"]')).toBeEnabled();
        if (await page.getByTestId("training-settings").getAttribute("open") !== null) await page.getByTestId("training-settings").locator("summary").first().click();
        if (task === "binary_classification") await capture(page, testInfo, `trained-${model}`);
        await page.getByRole("button", { name: "Перейти к анализу", exact: true }).click();
        const evaluated = page.waitForResponse((item) => item.url().endsWith("/api/projects/analyses/evaluations") && item.request().method() === "POST");
        await page.locator('[data-ruflex-action="evaluation.save"]').click();
        expect((await evaluated).status()).toBe(201);
        const evaluation = await (await evaluated).json();
        expect(evaluation.run_id).toBe(run.run_id);
        if (task === "binary_classification") {
          const threshold = page.waitForResponse((item) => item.url().endsWith("/api/projects/analyses/thresholds") && item.request().method() === "POST");
          await page.locator('[data-ruflex-action="threshold.select"]').click();
          expect((await threshold).status()).toBe(201);
        }
        await nav(page, "Доказательства").click();
        const methods = ["occlusion", ...(task === "binary_classification" ? extraMethods[family] : [])];
        let lastExplanationId: string | null = null;
        const checks: Array<{ method: string; status: string | null }> = [];
        for (const method of methods) {
          await page.getByLabel("Метод объяснения").selectOption(method);
          const generationStarted = page.waitForResponse((item) => item.url().endsWith("/api/projects/evidence/explanation-jobs") && item.request().method() === "POST");
          await page.locator('[data-ruflex-action="explanation.generate"]').click();
          const generationJob = await (await generationStarted).json();
          await expect(page.getByTestId("explanation-job")).toContainText(generationJob.job_id.slice(0, 12));
          await expect(page.getByTestId("explanation-job")).toContainText("SUCCEEDED", { timeout: 30_000 });
          const saved = await page.request.get(`http://127.0.0.1:8010/api/projects/${sessionId}/evidence/explanations/latest`);
          expect(saved.status()).toBe(200);
          const explanation = await saved.json();
          expect(explanation.run_id).toBe(run.run_id);
          expect(explanation.family).toBe(method);
          expect(explanation.explanation_id).not.toBe(lastExplanationId);
          lastExplanationId = explanation.explanation_id;
          await expect(page.getByTestId("explanation-attribution-chart").locator(".attribution-chart-row")).toHaveCount(run.feature_columns.length);
          const checkStarted = page.waitForResponse((item) => item.url().endsWith("/api/projects/evidence/explanation-check-jobs") && item.request().method() === "POST");
          await page.locator('[data-ruflex-action="explanation.check"]').click();
          const checkJob = await (await checkStarted).json();
          await expect(page.getByTestId("explanation-job")).toContainText(checkJob.job_id.slice(0, 12));
          await expect(page.getByTestId("explanation-job")).toContainText("SUCCEEDED", { timeout: 30_000 });
          await expect(page.getByTestId("explanation-check-status")).toHaveAttribute("data-status", /^(PASSED_AVAILABLE_CHECKS|WARNING)$/, { timeout: 30_000 });
          checks.push({ method, status: await page.getByTestId("explanation-check-status").getAttribute("data-status") });
        }
        await nav(page, "Анализ").click();
        await expect(page.getByRole("heading", { name: "Финальный тест закрыт", exact: true })).toBeVisible();
        await page.locator(".final-test-confirm input").check();
        const finalTest = page.waitForResponse((item) => item.url().endsWith("/api/projects/analyses/final-test") && item.request().method() === "POST");
        await page.locator('[data-ruflex-action="final_test.execute"]').click();
        expect((await finalTest).status()).toBe(201);
        const finalEvidence = await (await finalTest).json();
        expect(finalEvidence.run_id).toBe(run.run_id);
        expect(finalEvidence.evaluation_id).toBe(evaluation.evaluation_id);
        await expect(page.getByRole("heading", { name: "Результат финального теста сохранён отдельно" })).toBeVisible();
        await page.getByRole("button", { name: "Закрыть", exact: true }).click();
        await page.getByLabel("Папка проекта").fill(path);
        const reopened = page.waitForResponse((item) => item.url().endsWith("/api/projects/open") && item.request().method() === "POST");
        await page.getByRole("button", { name: "Открыть проект", exact: true }).click();
        const reopenedSessionId = (await (await reopened).json()).session_id;
        await nav(page, "Обучение").click();
        await expect(selector).toHaveValue(model);
        await expect(page.locator('[data-ruflex-action="training.run"]')).toBeDisabled();
        await expect(page.getByText(/Финальный тест для этого набора уже открыт/)).toBeVisible();
        const reopenedRun = await page.request.get(`http://127.0.0.1:8010/api/projects/${reopenedSessionId}/training/latest`);
        expect((await reopenedRun.json()).model_artifact_sha256).toBe(run.model_artifact_sha256);
        await nav(page, "Доказательства").click();
        await expect(page.getByTestId("explanation-attribution-chart")).toBeVisible();
        const reopenedExplanation = await page.request.get(`http://127.0.0.1:8010/api/projects/${reopenedSessionId}/evidence/explanations/latest`);
        expect((await reopenedExplanation.json()).explanation_id).toBe(lastExplanationId);
        await nav(page, "Анализ").click();
        await expect(page.getByRole("heading", { name: "Результат финального теста сохранён отдельно" })).toBeVisible();
        await testInfo.attach("persisted-model-route.json", { body: JSON.stringify({ model, task, run_id: run.run_id, model_artifact_sha256: run.model_artifact_sha256, metrics: run.validation_metrics, methods, checks, final_test_id: finalEvidence.final_test_id, reopen_verified: true, fixture_only: true }, null, 2), contentType: "application/json" });
        expect(browserErrors).toEqual([]);
      });
    }
  }
});

test("three-row schema example can be replaced explicitly with the full practice dataset", async ({ page }) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Run with VITE_RUFLEX_UI_LANG=ru");
  const path = join(tmpdir(), `ruflex-small-data-recovery-${Date.now()}`);
  await createProject(page, path, false);
  await nav(page, "Данные").click();
  await page.getByLabel("Данные CSV").fill("x,target\n10,0\n20,1\n30,1\n");
  await page.locator('[data-ruflex-action="dataset.inspect"]').click();
  await page.locator('[data-ruflex-action="dataset.confirm"]').click();
  await nav(page, "Обучение").click();
  await expect(page.getByTestId("training-small-dataset")).toBeVisible();
  await page.getByLabel("Модель для обучения").selectOption("decision_tree");
  await page.locator('[data-ruflex-action="training.run"]').click();
  await expect(page.getByRole("alert")).toContainText("В обучающей выборке остался только один класс");
  await expect(page.getByTestId("training-run-recovery")).toHaveCount(0);
  await page.getByRole("button", { name: "Перейти к данным", exact: true }).click();
  await page.getByRole("button", { name: "Загрузить учебные данные (80 строк)", exact: true }).click();
  await page.locator('[data-ruflex-action="dataset.inspect"]').click();
  await page.locator('[data-ruflex-action="dataset.confirm"]').click();
  await nav(page, "Обучение").click();
  await expect(page.getByTestId("training-small-dataset")).toHaveCount(0);
  await page.getByLabel("Модель для обучения").selectOption("decision_tree");
  const fitted = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/run") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="training.run"]').click();
  expect((await fitted).status()).toBe(201);
  await page.getByLabel("Модель для обучения").selectOption("mlp");
  await expect(page.getByText("Показан предыдущий результат. Модель, выбранная в настройках, ещё не обучена.")).toBeVisible();
  await expect(page.getByTestId("trained-model-name")).toContainText("Дерево решений");
});

test("an uploaded XLSX trains a classifier with categories and missing values and reopens unchanged", async ({ page }, testInfo) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Run with VITE_RUFLEX_UI_LANG=ru");
  test.setTimeout(90_000);
  const repoRoot = resolve("..");
  const python = process.env.RUFLEX_PYTHON ?? (existsSync(resolve(repoRoot, ".venv/bin/python")) ? resolve(repoRoot, ".venv/bin/python") : "python3");
  const script = [
    "from io import BytesIO", "import base64", "from openpyxl import Workbook",
    "book = Workbook()", "sheet = book.active", "sheet.append(['sample_id', 'temperature', 'torque', 'mode', 'target'])",
    "for index in range(96):\n    temperature = 10 + (index * 7) % 43\n    torque = 20 + (index * 11) % 53\n    sheet.append([f'sample-{index}', None if index % 13 == 0 else temperature, torque, 'service' if index % 3 == 0 else 'normal', int(temperature * .4 + torque * .6 >= 38)])",
    "buffer = BytesIO()", "book.save(buffer)", "print(base64.b64encode(buffer.getvalue()).decode())",
  ].join("\n");
  const buffer = Buffer.from(execFileSync(python, ["-c", script], { encoding: "utf8" }).trim(), "base64");
  const path = join(tmpdir(), `ruflex-xlsx-classifier-${Date.now()}`);
  await createProject(page, path, false);
  await nav(page, "Данные").click();
  await page.getByLabel("Файл CSV или XLSX").setInputFiles({ name: "measurements.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer });
  await expect(page.getByLabel("Целевой столбец", { exact: true }).locator('option[value="target"]')).toHaveCount(1);
  await page.getByLabel("Целевой столбец", { exact: true }).selectOption("target");
  await page.getByLabel("Роль столбца sample_id").selectOption("id");
  const imported = page.waitForResponse((item) => item.url().endsWith("/api/projects/dataset/import") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="dataset.import.confirm"]').click();
  expect((await imported).status()).toBe(200);
  const frozenContract = (await (await imported).json()).contract;
  expect(frozenContract.source_format).toBe("xlsx");
  expect(frozenContract.feature_columns).toEqual(["temperature", "torque", "mode"]);
  await capture(page, testInfo, "uploaded-xlsx");
  await nav(page, "Обучение").click();
  await page.getByLabel("Модель для обучения").selectOption("decision_tree");
  const fitted = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/run") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="training.run"]').click();
  expect((await fitted).status()).toBe(201);
  const run = await (await fitted).json();
  expect(run.feature_columns).toEqual(frozenContract.feature_columns);
  expect(run.validation_metrics.f1).toEqual(expect.any(Number));
  await page.getByRole("button", { name: "Объяснить прогноз", exact: true }).click();
  await expect(page.getByTestId("run-capability-negotiation")).toContainText("occlusion");
  await page.locator('[data-ruflex-action="explanation.generate"]').click();
  await expect(page.getByTestId("explanation-job")).toContainText("SUCCEEDED", { timeout: 30_000 });
  await expect(page.getByTestId("explanation-attribution-chart").locator(".attribution-chart-row")).toHaveCount(3);
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await page.getByLabel("Папка проекта").fill(path);
  const reopened = page.waitForResponse((item) => item.url().endsWith("/api/projects/open") && item.request().method() === "POST");
  await page.getByRole("button", { name: "Открыть проект", exact: true }).click();
  const sessionId = (await (await reopened).json()).session_id;
  const dataset = await page.request.get(`http://127.0.0.1:8010/api/projects/${sessionId}/dataset`);
  const restored = await dataset.json();
  expect(restored.contract).toEqual(frozenContract);
  expect(restored.profile.row_count).toBe(96);
  await nav(page, "Доказательства").click();
  await expect(page.getByTestId("explanation-attribution-chart").locator(".attribution-chart-row")).toHaveCount(3);
});

test("a completed practice project can switch to the user's CSV without mixing saved results", async ({ page }, testInfo) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Run with VITE_RUFLEX_UI_LANG=ru");
  test.setTimeout(120_000);
  const path = join(tmpdir(), `ruflex-practice-to-own-file-${Date.now()}`);
  await createProject(page, path, true);
  await page.getByLabel("Модель для обучения").selectOption("decision_tree");
  const initialFit = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/run") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="training.run"]').click();
  expect((await initialFit).status()).toBe(201);
  const practiceRun = await (await initialFit).json();
  await page.getByRole("button", { name: "Перейти к анализу", exact: true }).click();
  await page.locator('[data-ruflex-action="evaluation.save"]').click();
  await page.locator('[data-ruflex-action="threshold.select"]').click();
  await page.locator(".final-test-confirm input").check();
  const practiceFinal = page.waitForResponse((item) => item.url().endsWith("/api/projects/analyses/final-test") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="final_test.execute"]').click();
  expect((await practiceFinal).status()).toBe(201);
  const ownContract = await importUserCsv(page, "regression");
  expect(ownContract.dataset_fingerprint).not.toBe(practiceRun.dataset_fingerprint);
  await nav(page, "Обучение").click();
  await page.getByLabel("Модель для обучения").selectOption("linear_regression");
  await expect(page.getByText("Этот результат относится к предыдущему набору данных. Обучите модель на текущем наборе, чтобы продолжить.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Перейти к анализу", exact: true })).toBeDisabled();
  const ownFit = page.waitForResponse((item) => item.url().endsWith("/api/projects/training/run") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="training.run"]').click();
  expect((await ownFit).status()).toBe(201);
  const ownRun = await (await ownFit).json();
  expect(ownRun.dataset_fingerprint).toBe(ownContract.dataset_fingerprint);
  expect(ownRun.task).toBe("regression");
  expect(ownRun.feature_columns).toEqual(ownContract.feature_columns);
  await expect(page.getByTestId("trained-model-name")).toBeVisible();
  await expect(page.getByTestId("previous-analysis-history")).toBeVisible();
  await expect(page.getByTestId("previous-analysis-history")).not.toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: /Порог решения.*raw/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Оценка на финальном тесте.*правило зафиксировано/ })).toHaveCount(0);
  await capture(page, testInfo, "practice-to-own-csv");
  await page.getByRole("button", { name: "Перейти к анализу", exact: true }).click();
  await page.locator('[data-ruflex-action="evaluation.save"]').click();
  await expect(page.getByRole("heading", { name: "Финальный тест закрыт", exact: true })).toBeVisible();
  await expect(page.locator('[data-ruflex-action="threshold.select"]')).toHaveCount(0);
  await page.locator(".final-test-confirm input").check();
  const ownFinal = page.waitForResponse((item) => item.url().endsWith("/api/projects/analyses/final-test") && item.request().method() === "POST");
  await page.locator('[data-ruflex-action="final_test.execute"]').click();
  expect((await ownFinal).status()).toBe(201);
  expect((await (await ownFinal).json()).run_id).toBe(ownRun.run_id);
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await page.getByLabel("Папка проекта").fill(path);
  const opened = page.waitForResponse((item) => item.url().endsWith("/api/projects/open") && item.request().method() === "POST");
  await page.getByRole("button", { name: "Открыть проект", exact: true }).click();
  const sessionId = (await (await opened).json()).session_id;
  const dataset = await page.request.get(`http://127.0.0.1:8010/api/projects/${sessionId}/dataset`);
  expect((await dataset.json()).contract).toEqual(ownContract);
  const oldRun = await page.request.get(`http://127.0.0.1:8010/api/projects/${sessionId}/training/runs/${practiceRun.run_id}`);
  expect(oldRun.status()).toBe(200);
  expect((await oldRun.json()).model_artifact_sha256).toBe(practiceRun.model_artifact_sha256);
  await nav(page, "Анализ").click();
  await expect(page.getByRole("heading", { name: "Результат финального теста сохранён отдельно" })).toBeVisible();
});
