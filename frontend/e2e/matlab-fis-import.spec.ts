import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const matlabFis = `[System]
Name='tipper'
Type='mamdani'
AndMethod='min'
OrMethod='max'
ImpMethod='min'
AggMethod='max'
DefuzzMethod='centroid'

[Input1]
Name='temperature'
Range=[0 100]
MF1='low':'trimf',[0 0 50]

[Output1]
Name='risk'
Range=[0 1]
MF1='low':'trimf',[0 0 1]

[Rules]
1, 1 (1) : 1
`;

test("PRODUCT-12 preserves imported MATLAB FIS source provenance", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-fis-import-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Imported FIS");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "M", exact: true }).click();
  await page.getByLabel("MATLAB FIS file").setInputFiles({ name: "tipper.fis", mimeType: "text/plain", buffer: Buffer.from(matlabFis) });
  await expect(page.getByText(/MATLAB FIS imported as a canonical executable model.*source artifact/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "tipper", exact: true })).toBeVisible();
});
