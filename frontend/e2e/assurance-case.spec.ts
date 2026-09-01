import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";
test("PRODUCT-10 persists AssuranceCase independent gates without a trust score", async ({ page }) => {
  const path=join(tmpdir(),`ruflex-assurance-${Date.now()}`); await page.goto("/"); await page.getByLabel("Project path").fill(path); await page.getByLabel("Project name").fill("Assurance route"); await page.getByRole("button",{name:"Create project",exact:true}).click();
  await page.getByRole("button",{name:/Data.*No dataset/}).click(); await page.getByLabel("CSV data").fill("temperature,target\n10,0\n20,1\n30,1\n40,1\n"); await page.getByRole("button",{name:"Inspect dataset",exact:true}).click(); await page.getByRole("button",{name:"Confirm dataset contract",exact:true}).click();
  await page.getByRole("button",{name:"E",exact:true}).click(); await page.getByRole("button",{name:"Build AssuranceCase",exact:true}).click(); await expect(page.getByTestId("assurance-case")).toContainText("dataset contract"); await expect(page.getByTestId("assurance-case")).toContainText("NOT_AVAILABLE"); await expect(page.getByText("No universal trust score is produced.", {exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Export VerificationBundle",exact:true}).click(); await expect(page.getByTestId("verification-bundle")).toContainText("SHA-256");
  await page.getByRole("button",{name:"Close",exact:true}).click(); await page.getByLabel("Project path").fill(path); await page.getByRole("button",{name:"Open project",exact:true}).click(); await page.getByRole("button",{name:"E",exact:true}).click(); await expect(page.getByTestId("assurance-case")).toContainText("dataset contract");
});
