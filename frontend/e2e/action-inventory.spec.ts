import { expect, test } from "@playwright/test";
import inventory from "./action-inventory.json" with { type: "json" };
import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";

async function declaredActions(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const found: string[] = [];
  for (const entry of entries) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) found.push(...await declaredActions(path));
    if (entry.isFile() && /\.(ts|tsx)$/.test(entry.name)) {
      const source = await readFile(path, "utf8");
      found.push(...[...source.matchAll(/data-ruflex-action="([^"]+)"/g)].map((match) => match[1]));
    }
  }
  return found;
}

test("UI action inventory is complete and stable", async ({ page }) => {
  const ids = inventory.map((item) => item.action_id);
  expect(ids).toHaveLength(39);
  expect(new Set(ids).size).toBe(ids.length);
  for (const item of inventory) {
    expect(item.workspace).not.toEqual("");
    expect(item.canonical_outcome).not.toEqual("");
    expect(item.e2e_spec).toEqual("action-inventory.spec.ts");
  }
  const sourceActions = await declaredActions(resolve(import.meta.dirname, "../src"));
  expect([...new Set(sourceActions)].sort()).toEqual([...ids].sort());
  await page.goto("/");
  await expect(page.locator('[data-ruflex-action="project.create"]')).toBeVisible();
});
