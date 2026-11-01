import { expect, test, type Page } from "@playwright/test";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { mkdirSync } from "node:fs";
import { openTrainingSettings } from "./helpers/trainingSettings";

const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name, exact: true });
async function dataset(page: Page, id: string) {
  await page.goto("/");
  const path = join(tmpdir(), `ruflex-library-${id}-${Date.now()}`);
  await page.getByLabel("Папка проекта").fill(path);
  await page.getByLabel("Название проекта").fill("Учебные наборы и история");
  await page.getByLabel("Тип нового проекта").selectOption("empty");
  const created = page.waitForResponse((r) => r.url().endsWith("/api/projects") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  const session = (await (await created).json()).session_id;
  await nav(page, "Данные").click();
  await page.getByText("Выбрать учебный набор данных", { exact: true }).click();
  await page.getByLabel("Учебный набор", { exact: true }).selectOption(id);
  await expect(page.getByTestId("dataset-library")).toContainText("синтетические");
  await page.getByRole("button", { name: "Подставить набор", exact: true }).click();
  const confirmed = page.waitForResponse((r) => r.url().endsWith("/dataset/confirm") && r.request().method() === "POST");
  await page.locator('[data-ruflex-action="dataset.continue"]').click();
  expect((await confirmed).status()).toBe(200);
  const contract = (await (await confirmed).json()).contract;
  expect(contract.feature_columns.length).toBeGreaterThanOrEqual(8);
  return { session, contract, path };
}
async function fit(page: Page, model: string) {
  await page.getByLabel("Модель для обучения").selectOption(model);
  if (["flat_neuro_fuzzy", "random_forest"].includes(model)) {
    await openTrainingSettings(page);
    if (model === "flat_neuro_fuzzy") {
      await page.getByLabel("Эпохи", { exact: true }).fill("4");
      await page.getByLabel("Правил на слой", { exact: true }).fill("4");
    } else await page.getByLabel("Число деревьев", { exact: true }).fill("8");
  }
  const fitted = page.waitForResponse((r) => r.url().endsWith("/training/run") && r.request().method() === "POST");
  await page.locator('[data-ruflex-action="training.run"]').click();
  expect((await fitted).status()).toBe(201);
  return (await (await fitted).json());
}
async function evaluate(page: Page) {
  await page.getByRole("button", { name: "Перейти к анализу", exact: true }).click();
  const evaluated = page.waitForResponse((r) => r.url().endsWith("/analyses/evaluations") && r.request().method() === "POST");
  await page.locator('[data-ruflex-action="evaluation.save"]').click();
  const response = await evaluated;
  expect(response.status()).toBe(201);
  return response.json();
}
async function capture(page: Page, name: string) {
  if (process.env.RUFLEX_CAPTURE_LIBRARY_SCREENSHOTS !== "1") return;
  const folder = resolve("..", "docs", "qa", "screenshots", "dataset-library");
  mkdirSync(folder, { recursive: true });
  await page.screenshot({ path: join(folder, `${name}.png`), animations: "disabled" });
}
test.beforeEach(() => test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Russian library route"));

test("soil regression and historical evaluation restore the exact older model without writing", async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1280, height: 850 });
  const { session, contract, path } = await dataset(page, "soil");
  await expect(page.getByTestId("synthetic-practice-context")).toContainText("Синтетический");
  expect(contract.feature_columns).toContain("Тип_грунта");
  const firstRun = await fit(page, "linear_regression");
  const first = await evaluate(page);
  await expect(page.getByTestId("prediction-distribution")).toContainText(`${first.validation_row_count}`);
  await capture(page, "soil-validation");
  await nav(page, "Обучение").click();
  const secondRun = await fit(page, "decision_tree");
  const second = await evaluate(page);
  expect(second.run_id).toBe(secondRun.run_id);
  await nav(page, "Проект").click();
  const history = page.getByTestId("lineage-object-list");
  const older = history.locator(`[data-lineage-object-id="${first.evaluation_id}"]`);
  await expect(older).toBeVisible();
  await history.getByRole("button", { name: /Преобразование признаков/ }).first().click();
  await expect(page.getByTestId("lineage-metadata")).toContainText("Модель не запускается");
  await expect(history.getByRole("button", { name: /Обученная модель: Линейная регрессия/ })).toBeVisible();
  await capture(page, "history-list");
  await page.getByRole("button", { name: "Граф связей", exact: true }).click();
  await expect(page.locator(".project-lineage .lineage-node").first()).toBeVisible();
  await page.getByRole("button", { name: "Список объектов", exact: true }).click();
  let writes = 0;
  page.on("request", (r) => { if (r.method() === "POST") writes++; });
  await page.route(`**/training/runs/${firstRun.run_id}`, (route) => route.fulfill({ status: 503, json: { detail: "history model temporarily unavailable" } }), { times: 1 });
  await older.click();
  await expect(page.getByTestId("lineage-object-load-error")).toBeVisible();
  await page.getByTestId("lineage-object-load-error").getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(page.locator(".evaluation-footer")).toContainText(firstRun.run_id.slice(0, 12));
  await nav(page, "Обучение").click();
  await expect(page.getByTestId("trained-model-name")).toContainText("Линейная регрессия");
  expect(writes).toBe(0);
  const latest = await page.request.get(`http://127.0.0.1:8010/api/projects/${session}/training/latest`);
  expect((await latest.json()).run_id).toBe(secondRun.run_id);
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await page.getByLabel("Папка проекта").fill(path);
  await page.getByRole("button", { name: "Открыть проект", exact: true }).click();
  await nav(page, "Обучение").click();
  await expect(page.getByTestId("trained-model-name")).toContainText("Дерево решений");
  await expect(page.getByTestId("synthetic-practice-context")).toContainText("Синтетический");
});

test("equipment has ten features and real TreeSHAP and permutation SHAP", async ({ page }) => {
  test.setTimeout(90_000);
  const { session } = await dataset(page, "equipment");
  const run = await fit(page, "decision_tree");
  await evaluate(page);
  await expect(page.getByTestId("prediction-distribution")).toBeVisible();
  await nav(page, "Доказательства").click();
  await expect(page.getByRole("button", { name: "GradientSHAP · градиенты", exact: true })).toBeDisabled();
  for (const [key, label] of [["tree_shap", "TreeSHAP · деревья"], ["shap", "SHAP · перестановки"]]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await page.locator('[data-ruflex-action="explanation.generate"]').click();
    await expect(page.getByTestId("explanation-attribution-chart")).toBeVisible();
    await expect(page.getByTestId("explanation-attribution-chart").locator(".attribution-chart-row")).toHaveCount(8);
    await expect(page.getByTestId("explanation-job")).toContainText("Объяснение сохранено", { timeout: 30_000 });
    await expect(page.getByText("Ниже сохранён результат другого метода.", { exact: false })).toHaveCount(0);
    await expect.poll(async () => {
      const result = await page.request.get(`http://127.0.0.1:8010/api/projects/${session}/evidence/explanations/latest`);
      const value = await result.json();
      expect(value.run_id).toBe(run.run_id);
      return value.family;
    }).toBe(key);
    expect(run.feature_columns).toHaveLength(10);
    await capture(page, key);
  }
});

test("neuro-fuzzy equipment exposes and executes GradientSHAP", async ({ page }) => {
  test.setTimeout(90_000);
  const { session } = await dataset(page, "equipment");
  const run = await fit(page, "flat_neuro_fuzzy");
  await page.getByRole("button", { name: "Объяснить прогноз", exact: true }).click();
  await page.getByRole("button", { name: "GradientSHAP · градиенты", exact: true }).click();
  await page.locator('[data-ruflex-action="explanation.generate"]').click();
  await expect(page.getByTestId("explanation-job")).toContainText("Объяснение сохранено", { timeout: 30_000 });
  await expect(page.getByTestId("explanation-attribution-chart")).toBeVisible();
  const saved = await page.request.get(`http://127.0.0.1:8010/api/projects/${session}/evidence/explanations/latest`);
  expect(await saved.json()).toMatchObject({ family: "gradient_shap", run_id: run.run_id });
  await capture(page, "gradient_shap");
});

test("energy regression uses eight-feature data through the normal workflow", async ({ page }) => {
  test.setTimeout(90_000);
  const { contract } = await dataset(page, "energy");
  expect(contract.feature_columns).toHaveLength(8);
  const run = await fit(page, "random_forest");
  const result = await evaluate(page);
  expect(result.run_id).toBe(run.run_id);
  await expect(page.getByTestId("prediction-distribution")).toBeVisible();
});
