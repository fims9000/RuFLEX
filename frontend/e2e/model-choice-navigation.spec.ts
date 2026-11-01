import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("Models guides a new Russian-language user to data and then to trainable model choice", async ({ page }) => {
  test.skip(process.env.VITE_RUFLEX_UI_LANG !== "ru", "Run with VITE_RUFLEX_UI_LANG=ru");
  await page.goto("/");
  await page.getByLabel("Папка проекта").fill(join(tmpdir(), `ruflex-model-choice-${Date.now()}`));
  await page.getByLabel("Название проекта").fill("Выбор модели");
  await page.getByRole("button", { name: "Создать проект" }).click();
  await page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name: "Модели" }).click();
  await expect(page.getByTestId("model-route-guide")).toContainText("MLP");
  await expect(page.getByText("Нет модели FIS", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Создать модель из данных" })).toHaveCount(0);
  await expect(page.getByText("No such file or directory")).toHaveCount(0);
  await page.getByRole("button", { name: "Сначала сохранить данные" }).click();
  await page.getByRole("button", { name: "Загрузить учебные данные (80 строк)" }).click();
  await page.getByRole("button", { name: "Проверить данные" }).click();
  await page.getByRole("button", { name: "Сохранить набор данных" }).click();
  await page.getByRole("navigation", { name: "Разделы Studio" }).getByRole("button", { name: "Модели" }).click();
  await page.getByRole("button", { name: "Выбрать модель для обучения" }).click();
  const model = page.getByLabel("Модель для обучения");
  await expect(model).toBeEnabled();
  await expect(model.locator("option")).toHaveCount(6);
  await model.selectOption("mlp");
  await expect(page.getByLabel("Нейронов в скрытом слое")).toBeVisible();
});
