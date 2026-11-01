import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { mkdirSync } from "node:fs";

test("Russian analysis and requirement checks explain results without exposed hashes", async ({ page }) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Russian presentation");
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1280, height: 850 });
  await page.goto("/");
  await page.getByLabel("Папка проекта").fill(join(tmpdir(), `ruflex-readable-${Date.now()}`));
  await page.getByLabel("Название проекта").fill("Понятные результаты");
  await page.getByLabel("Тип нового проекта").selectOption("practice");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  await page.getByLabel("Модель для обучения").selectOption("decision_tree");
  const fitted = page.waitForResponse((r) => r.url().endsWith("/training/run") && r.request().method() === "POST");
  await page.locator('[data-ruflex-action="training.run"]').click();
  expect((await fitted).status()).toBe(201);
  const technical = page.getByTestId("technical-project-files");
  await expect(technical).not.toHaveAttribute("open", "");
  await expect(technical.locator("code").first()).not.toBeVisible();
  await page.getByRole("button", { name: "Перейти к анализу", exact: true }).click();
  await page.locator('[data-ruflex-action="evaluation.save"]').click();
  const gate = page.locator(".final-test-gate");
  await expect(gate).toContainText("Это итоговая проверка на данных");
  await expect(gate).not.toContainText("Validation remains");
  await expect(page.locator('[data-ruflex-action="final_test.execute"]')).toBeDisabled();
  await page.getByLabel("Нижняя граница").fill("");
  await page.getByLabel("Верхняя граница").fill("");
  await page.locator('[data-ruflex-action="slice.create"]').click();
  await expect(page.getByRole("alert")).toContainText("Укажите хотя бы одну границу");
  await page.getByLabel("Нижняя граница").fill("0");
  await page.locator('[data-ruflex-action="slice.create"]').click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const nav = page.getByRole("navigation", { name: "Разделы Studio" });
  await nav.getByRole("button", { name: "Доказательства" }).click();
  await page.locator('[data-ruflex-action="explanation.generate"]').click();
  await expect(page.getByTestId("explanation-readable-summary")).toContainText("самый большой вклад");
  await expect(page.getByTestId("explanation-attribution-chart")).toBeVisible();
  await page.locator('[data-ruflex-action="behavior.run"]').click();
  const readable = page.getByTestId("behavior-readable-result");
  await expect(readable).toContainText("Модель выдала");
  await expect(readable).toContainText("Допустимые значения: от 0 до 1");
  await expect(readable.getByRole("img")).toBeVisible();
  await expect(page.getByTestId("behavior-result")).not.toContainText("Output remains");
  if (process.env.RUFLEX_CAPTURE_READABLE_SCREENSHOTS === "1") {
    const folder = resolve("..", "docs", "qa", "screenshots", "readable-russian");
    mkdirSync(folder, { recursive: true });
    await readable.scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(folder, "behavior-range.png"), animations: "disabled" });
  }
  await page.getByLabel("Минимум выхода", { exact: true }).fill("2");
  await page.getByLabel("Максимум выхода", { exact: true }).fill("3");
  await page.locator('[data-ruflex-action="behavior.run"]').click();
  await expect(readable).toContainText("требование нарушено");
  await expect(page.getByTestId("behavior-counterexample")).toContainText("Пример нарушения требования");
  await expect(page.getByTestId("behavior-counterexample")).not.toContainText("Observed output");
});

test("legacy failed StudyJob is disclosed as history, not repeated current adapter errors", async ({ page }) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Russian presentation");
  await page.route("**/training/study-jobs", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill({ json: [{ job_id: "old-job", name: "Saved failed study", model_kind: "decision_tree", status: "FAILED", selection_metric: "f1", cancel_requested: false, execution_backend: "LOCAL", execution_config: {}, seed_states: [42, 43, 44].map((seed) => ({ seed, split_seed: 42, training_seed: seed, status: "FAILED", error: "Unsupported or unavailable model adapter for 'decision_tree'.", run_id: null })), error: "Fewer than three seed runs succeeded; no scientific selection was produced.", study_id: null }] });
  });
  await page.goto("/");
  await page.getByLabel("Папка проекта").fill(join(tmpdir(), `ruflex-old-study-${Date.now()}`));
  await page.getByLabel("Название проекта").fill("История неудачного запуска");
  await page.getByLabel("Тип нового проекта").selectOption("practice");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  const summary = page.getByTestId("study-job-summary");
  await expect(summary).toContainText("сохранённый результат прошлого запуска");
  await expect(summary).toContainText("Успешных запусков: 0 из 3");
  await expect(summary.locator("code").first()).not.toBeVisible();
  await summary.getByText("Технические подробности запуска").click();
  await expect(summary.locator("code").first()).toContainText("Unsupported or unavailable");
});
