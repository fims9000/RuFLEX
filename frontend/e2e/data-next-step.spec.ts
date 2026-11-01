import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test.beforeEach(async ({ page }) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Russian user workflow");
  await page.goto("/");
  await page.getByLabel("Папка проекта").fill(join(tmpdir(), `ruflex-data-next-${Date.now()}-${Math.random().toString(16).slice(2)}`));
  await page.getByLabel("Название проекта").fill("Проверка перехода от данных к модели");
  await page.getByLabel("Тип нового проекта").selectOption("empty");
  const created = page.waitForResponse((r) => r.url().endsWith("/api/projects") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  expect((await created).status()).toBe(201);
  await page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name: "Данные", exact: true }).click();
});

for (const task of ["binary_classification", "regression"] as const) {
  test(`pasted ${task}: automatic preview → next → model → fit without separate inspect/save`, async ({ page }) => {
    let writes = 0;
    page.on("request", (request) => { if (request.url().endsWith("/dataset/confirm")) writes += 1; });
    const csv = "x,target\n" + Array.from({ length: 80 }, (_, i) => `${i},${task === "regression" ? i * .5 + 2 : i % 2}`).join("\n");
    await page.getByLabel("Данные CSV", { exact: true }).fill(csv);
    await page.getByLabel("Задача", { exact: true }).selectOption(task);
    const next = page.getByRole("button", { name: "Далее: выбрать модель", exact: true });
    await expect(page.getByLabel("Роль столбца x")).toBeVisible();
    await expect(next).toBeEnabled();
    expect(writes).toBe(0); // Preview must not silently persist a scientific dataset.
    const confirmed = page.waitForResponse((r) => r.url().endsWith("/dataset/confirm"));
    await next.evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
    expect((await confirmed).status()).toBe(200);
    const selector = page.getByLabel("Модель для обучения");
    await expect(selector).toBeVisible();
    expect(writes).toBe(1);
    await selector.selectOption(task === "regression" ? "linear_regression" : "decision_tree");
    const fitted = page.waitForResponse((r) => r.url().endsWith("/training/run") && r.request().method() === "POST");
    await page.locator('[data-ruflex-action="training.run"]').click();
    expect((await fitted).status()).toBe(201);
    const run = await (await fitted).json();
    expect(run.task).toBe(task);
    await page.getByRole("button", { name: "Перейти к анализу", exact: true }).click();
    await page.locator('[data-ruflex-action="evaluation.save"]').click();
    await expect(page.getByRole("heading", { name: "Финальный тест закрыт", exact: true })).toBeVisible();
    await page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name: "Данные", exact: true }).click();
    await next.click(); // An unchanged saved dataset must not be saved again.
    await expect(selector).toBeVisible();
    expect(writes).toBe(1);
  });
}

test("invalid target stays on data; corrected target proceeds without a second inspection", async ({ page }) => {
  await page.getByLabel("Данные CSV", { exact: true }).fill("x,target\n" + Array.from({ length: 40 }, (_, i) => `${i},${i % 2}`).join("\n"));
  await expect(page.getByLabel("Роль столбца x")).toBeVisible();
  await page.getByLabel("Целевой столбец", { exact: true }).fill("does_not_exist");
  const next = page.getByRole("button", { name: "Далее: выбрать модель", exact: true });
  await next.click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("Данные CSV", { exact: true })).toBeVisible();
  await page.getByLabel("Целевой столбец", { exact: true }).fill("target");
  await next.click();
  await expect(page.getByLabel("Модель для обучения")).toBeVisible();
});

test("saved file roles never replace the source with the default CSV editor", async ({ page }) => {
  const csv = "x,target\n" + Array.from({ length: 40 }, (_, i) => `${i},${i % 2}`).join("\n");
  await page.getByLabel("Файл CSV или XLSX").setInputFiles({ name: "own.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.getByLabel("Целевой столбец", { exact: true }).locator('option[value="target"]')).toHaveCount(1);
  await page.getByLabel("Целевой столбец", { exact: true }).selectOption("target");
  const next = page.getByRole("button", { name: "Далее: выбрать модель", exact: true });
  const imported = page.waitForResponse((r) => r.url().endsWith("/dataset/import"));
  await next.click();
  expect((await imported).status()).toBe(200);
  await expect(page.getByLabel("Модель для обучения")).toBeVisible();
  await page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name: "Данные", exact: true }).click();
  await page.getByLabel("Задача", { exact: true }).selectOption("regression");
  let writes = 0;
  page.on("request", (r) => { if (r.url().endsWith("/dataset/confirm") || r.url().endsWith("/dataset/import")) writes += 1; });
  await next.click();
  await expect(page.getByRole("alert")).toContainText("Сохранённые данные не изменены");
  expect(writes).toBe(0);
  await page.getByLabel("Задача", { exact: true }).selectOption("binary_classification");
  await next.click();
  await expect(page.getByLabel("Модель для обучения")).toBeVisible();
  expect(writes).toBe(0);
});
