import { expect, test } from "@playwright/test";
import inventory from "./action-inventory.json" with { type: "json" };

test("UI action inventory is complete and stable", async ({ page }) => {
  const ids = inventory.map((item) => item.action_id);
  expect(ids).toEqual([
    "project.create", "dataset.confirm", "training.run", "study.start",
    "stability.freeze", "final_test.execute", "explanation.generate", "bundle.export",
  ]);
  for (const item of inventory) {
    expect(item.workspace).not.toEqual("");
    expect(item.canonical_outcome).not.toEqual("");
    expect(item.e2e_spec).toEqual("action-inventory.spec.ts");
  }
  await page.goto("/");
  await expect(page.locator('[data-ruflex-action="project.create"]')).toBeVisible();
});
