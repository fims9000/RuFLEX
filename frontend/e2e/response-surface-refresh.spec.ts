import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("response surface refreshes when a fixed run input changes", async ({ page }) => {
  const projectPath = join(tmpdir(), `ruflex-surface-${Date.now()}`);
  const requests: Array<{ fixed_inputs: Record<string, number> }> = [];
  await page.route("**/api/projects/fis/response-surface", async (route) => {
    const request = route.request().postDataJSON();
    requests.push(request);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        fis_id: request.spec.fis_id,
        semantic_hash: request.spec.semantic_hash,
        x_variable: request.x_variable,
        y_variable: request.y_variable,
        fixed_inputs: request.fixed_inputs,
        resolution: 2,
        samples: [
          { x: 0, y: 0, output: 0 },
          { x: 1, y: 0, output: 0.5 },
          { x: 0, y: 1, output: 0.5 },
          { x: 1, y: 1, output: 1 },
        ],
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(projectPath);
  await page.getByLabel("Project name").fill("Response surface refresh");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByLabel("CSV data").fill("temperature,torque,pressure,target\n10,20,0.2,0\n20,50,0.5,1\n30,80,0.9,1\n40,100,0.7,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: /New FIS from dataset/ }).click();
  await page.getByRole("button", { name: "Create FIS from dataset", exact: true }).click();

  await expect.poll(() => requests.length).toBeGreaterThan(0);
  const initialRequestCount = requests.length;
  await page.getByLabel("pressure", { exact: true }).fill("not numeric");
  await expect(page.getByRole("alert").filter({ hasText: "Invalid: pressure" })).toBeVisible();
  expect(requests).toHaveLength(initialRequestCount);
  await page.getByLabel("pressure", { exact: true }).fill("0.9");
  await expect.poll(() => requests.length).toBeGreaterThan(1);
  await expect.poll(() => requests.at(-1)?.fixed_inputs.pressure).toBe(0.9);
});
