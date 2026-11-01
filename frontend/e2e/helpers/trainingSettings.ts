import { expect, type Page } from "@playwright/test";

export async function openTrainingSettings(page: Page) {
  const settings = page.getByTestId("training-settings");
  await expect(settings).toBeVisible();
  if (await settings.getAttribute("open") === null) await settings.locator("summary").first().click();
}
