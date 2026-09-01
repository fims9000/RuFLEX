import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("PRODUCT-09 persists exact finite Decision Tree Exhaustive Lab evidence", async ({ page }) => {
  test.setTimeout(60_000); const path=join(tmpdir(), `ruflex-exhaustive-${Date.now()}`); const rows=["temperature,torque,target"];
  for(let i=0;i<45;i+=1) rows.push(`${10+i},${20+(i*7)%60},${10+i+20+(i*7)%60>62?1:0}`);
  await page.goto("/"); await page.getByLabel("Project path").fill(path); await page.getByLabel("Project name").fill("Exhaustive route"); await page.getByRole("button",{name:"Create project",exact:true}).click();
  await page.getByRole("button",{name:/Data.*No dataset/}).click(); await page.getByLabel("CSV data").fill(`${rows.join("\n")}\n`); await page.getByRole("button",{name:"Inspect dataset",exact:true}).click(); await page.getByRole("button",{name:"Confirm dataset contract",exact:true}).click();
  await page.getByRole("button",{name:"S",exact:true}).click(); await page.getByLabel("Training model").selectOption("decision_tree"); await page.getByRole("button",{name:"Run real training",exact:true}).click(); await expect(page.locator(".run-provenance")).toContainText("model artifact persisted",{timeout:30000});
  await page.getByRole("button",{name:"E",exact:true}).click(); await page.getByRole("button",{name:"Enumerate exact Decision Tree paths",exact:true}).click(); await expect(page.getByTestId("exhaustive-result")).toContainText("EXACT_FINITE_STRUCTURE",{timeout:15000}); await expect(page.getByText(/does not claim exhaustive explanation/)).toBeVisible();
  await page.getByRole("button",{name:"Close",exact:true}).click(); await page.getByLabel("Project path").fill(path); await page.getByRole("button",{name:"Open project",exact:true}).click(); await page.getByRole("button",{name:"E",exact:true}).click(); await expect(page.getByTestId("exhaustive-result")).toContainText("EXACT_FINITE_STRUCTURE",{timeout:15000});
});
