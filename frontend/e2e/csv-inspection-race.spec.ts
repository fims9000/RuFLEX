import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("a stale CSV preview cannot replace the preview for edited input", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-csv-preview-race-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("CSV preview race");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();

  let releaseFirstInspection!: () => void;
  let markFirstInspectionStarted!: () => void;
  const firstInspectionGate = new Promise<void>((resolve) => { releaseFirstInspection = resolve; });
  const firstInspectionStarted = new Promise<void>((resolve) => { markFirstInspectionStarted = resolve; });
  let firstInspectionText = "";
  await page.route("**/api/projects/dataset/inspect", async (route) => {
    const body = route.request().postDataJSON() as { csv_text?: string };
    if (body.csv_text?.includes("old-preview")) {
      firstInspectionText = body.csv_text;
      markFirstInspectionStarted();
      await firstInspectionGate;
    }
    await route.continue();
  });

  await page.getByLabel("CSV data").fill("old-preview,target\na,0\nb,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await firstInspectionStarted;
  await page.getByLabel("CSV data").fill("new-preview,target\na,0\nb,1\nc,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 3 · columns: 2/)).toBeVisible();

  try {
    const staleResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/dataset/inspect")
      && response.request().method() === "POST"
      && (response.request().postDataJSON() as { csv_text?: string }).csv_text === firstInspectionText,
    );
    releaseFirstInspection();
    await staleResponse;
    await expect(page.getByText(/Rows: 3 · columns: 2/)).toBeVisible();
    await expect(page.getByText(/Rows: 2 · columns: 2/)).toHaveCount(0);
  } finally {
    releaseFirstInspection();
  }
});

test("a late inline CSV inspection cannot reintroduce roles after file selection", async ({ page }) => {
  const path = join(tmpdir(), `ruflex-csv-file-race-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Source inspection race");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();

  let releaseCsv!: () => void;
  let markCsvStarted!: () => void;
  const csvGate = new Promise<void>((resolve) => { releaseCsv = resolve; });
  const csvStarted = new Promise<void>((resolve) => { markCsvStarted = resolve; });
  await page.route("**/api/projects/dataset/inspect", async (route) => {
    markCsvStarted();
    await csvGate;
    await route.continue();
  });

  await page.getByLabel("CSV data").fill("old_id,old_target\na,0\nb,1\n");
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await csvStarted;
  await page.getByLabel("Dataset CSV or XLSX file").setInputFiles({
    name: "new.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("temperature,outcome\n10,0\n20,1\n"),
  });
  await expect(page.getByLabel("Selected file schema preview")).toContainText("new.csv");
  try {
    const staleResponse = page.waitForResponse((response) => response.url().endsWith("/api/projects/dataset/inspect"));
    releaseCsv();
    await staleResponse;
    await expect(page.getByLabel("Selected file schema preview")).toContainText("new.csv");
    await expect(page.getByRole("combobox", { name: "Role for old_id" })).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "ID columns" })).toHaveValue("");
  } finally {
    releaseCsv();
  }
});
