import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const projectPath = () => join(tmpdir(), `ruflex-repro-${Date.now()}-${Math.random().toString(16).slice(2)}`);
function csv() { const rows=["temperature,torque,target"]; for(let i=0;i<50;i+=1) rows.push(`${10+i*.7},${20+(i*9)%60},${10+i*.7+20+(i*9)%60>60?1:0}`); return `${rows.join("\n")}\n`; }

test("PRODUCT-08 persists separate cross-run prediction and explanation reproducibility evidence", async ({ page }) => {
  test.setTimeout(90_000); const path=projectPath(); await page.goto("/");
  await page.getByLabel("Project path").fill(path); await page.getByLabel("Project name").fill("Repro route"); await page.getByRole("button", {name:"Create project", exact:true}).click();
  await page.getByRole("button", {name:/Data.*No dataset/}).click(); await page.getByLabel("CSV data").fill(csv()); await page.getByRole("button", {name:"Inspect dataset",exact:true}).click(); await page.getByRole("button", {name:"Confirm dataset contract",exact:true}).click();
  await page.getByRole("button", {name:"S",exact:true}).click(); await page.getByLabel("Training model").selectOption("logistic_regression"); await page.getByRole("button", {name:"Run real training",exact:true}).click(); await expect(page.locator(".run-provenance")).toContainText("model artifact persisted",{timeout:30000});
  await page.getByRole("button", {name:"E",exact:true}).click(); const generate=page.getByRole("button", {name:"Generate explanation",exact:true}); await generate.click(); await expect(generate).toBeEnabled(); await page.getByLabel("temperature").fill("30"); await generate.click(); await expect(generate).toBeEnabled();
  await page.getByRole("button", {name:"S",exact:true}).click(); await page.getByLabel("Training model").selectOption("decision_tree"); await page.getByRole("button", {name:"Run real training",exact:true}).click(); await expect(page.locator(".run-provenance")).toContainText("model artifact persisted",{timeout:30000});
  await page.getByRole("button", {name:"E",exact:true}).click(); await generate.click(); await expect(generate).toBeEnabled(); await page.getByLabel("temperature").fill("30"); await generate.click(); await expect(generate).toBeEnabled();
  const checks=page.locator('.comparison-choice input[type="checkbox"]'); await expect(checks).toHaveCount(4); for(let i=0;i<4;i+=1) await checks.nth(i).check(); await page.getByRole("button", {name:"Compare explanation reproducibility",exact:true}).click();
  await expect(page.getByTestId("reproducibility-result")).toContainText("PREDICTION AGREEMENT",{timeout:15000}); await expect(page.getByTestId("reproducibility-result")).toContainText("EXPLANATION AGREEMENT"); await expect(page.getByText(/must not be interpreted as explanation stability/)).toBeVisible();
  let reproducibilityReadFailed = false;
  await page.route(`**/api/projects/*/evidence/explanation-reproducibility/latest`, async (route) => {
    if (!reproducibilityReadFailed) {
      reproducibilityReadFailed = true;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporary reproducibility read failure" }) });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", {name:"Close",exact:true}).click(); await page.getByLabel("Project path").fill(path); await page.getByRole("button", {name:"Open project",exact:true}).click(); await page.getByRole("button", {name:"E",exact:true}).click(); await expect(page.getByTestId("reproducibility-hydration-error")).toContainText("Temporary reproducibility read failure"); await page.getByRole("button", {name:"Retry reproducibility analysis",exact:true}).click(); await expect(page.getByTestId("reproducibility-result")).toContainText("EXPLANATION AGREEMENT",{timeout:15000});
  await page.getByRole("button", { name: "P", exact: true }).click();
  const reproducibilityNode = page.locator(".lineage-explanation_reproducibility").first();
  await expect(reproducibilityNode).toBeVisible();
  await reproducibilityNode.click({ force: true });
  await expect(page.getByTestId("reproducibility-result")).toContainText("PREDICTION AGREEMENT");
  await expect(page.getByTestId("reproducibility-result")).toContainText("EXPLANATION AGREEMENT");
});
