import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-playwright-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

async function createProject(page: import("@playwright/test").Page, path: string, name = "Pump-01") {
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.locator(".project-identity")).toContainText(name);
}

test("E2E-01 creates a project and exposes it in Explorer and Properties", async ({ page }) => {
  await createProject(page, projectPath("create"));
  await expect(page.locator(".project-identity")).toContainText("Pump-01");
  await expect(page.locator(".project-object-tree")).toContainText("Pump-01");
  await expect(page.getByText(/^ID: [0-9a-f-]{36}$/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Optional quick start" })).toContainText("does not start training or access the locked test split");
  await page.getByRole("button", { name: "Review or import data", exact: true }).click();
  await expect(page.locator(".data-workspace")).toBeVisible();
  await expect(page.getByLabel("Target")).toHaveValue("target");
});

test("E2E-02 saves metadata, closes, and reopens it", async ({ page }) => {
  const path = projectPath("reopen");
  await createProject(page, path, "Reopen");
  await page.getByLabel("Description").fill("Preserved description");
  await page.getByRole("button", { name: "Update description", exact: true }).click();
  await expect(page.getByText("Updated Reopen", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByText("Description: Preserved description", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Optional quick start" })).toContainText("Start with your data");
  await expect(page.getByTestId("project-integrity")).toContainText("PASS");
});

test("serializes create and recent-project open requests", async ({ page }) => {
  const path = projectPath("lifecycle-serialization");
  let createRequests = 0;
  let openRequests = 0;
  let releaseCreate: () => void = () => {};
  let releaseOpen: () => void = () => {};
  let createStarted: () => void = () => {};
  let openStarted: () => void = () => {};
  const createStartedPromise = new Promise<void>((resolve) => { createStarted = resolve; });
  const openStartedPromise = new Promise<void>((resolve) => { openStarted = resolve; });

  await page.route("**/api/projects", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    createRequests += 1;
    createStarted();
    await new Promise<void>((resolve) => { releaseCreate = resolve; });
    await route.continue();
  });
  await page.route("**/api/projects/open", async (route) => {
    openRequests += 1;
    openStarted();
    await new Promise<void>((resolve) => { releaseOpen = resolve; });
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Project name").fill("Lifecycle serialization");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await createStartedPromise;
  await expect(page.getByRole("button", { name: "Creating project…", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Open project", exact: true })).toBeDisabled();
  releaseCreate();
  await expect(page.locator(".project-identity")).toContainText("Lifecycle serialization");
  expect(createRequests).toBe(1);

  await page.getByRole("button", { name: "Close", exact: true }).click();
  const recentProject = page.locator(".recent-project-item").filter({ hasText: "Lifecycle serialization" });
  await recentProject.click();
  await openStartedPromise;
  await expect(recentProject).toBeDisabled();
  await expect(page.getByRole("button", { name: "Create project", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Open project", exact: true })).toBeDisabled();
  releaseOpen();
  await expect(page.locator(".project-identity")).toContainText("Lifecycle serialization");
  expect(openRequests).toBe(1);
});

test("E2E-02b keeps dataset import paused on a state-read failure and enables it after retry confirms absence", async ({ page }) => {
  let datasetReads = 0;
  await page.route("**/api/projects/*/dataset", async (route) => {
    datasetReads += 1;
    if (datasetReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "dataset state temporarily unavailable" }) });
    }
    return route.continue();
  });
  await createProject(page, projectPath("dataset-state-retry"), "Dataset state recovery");
  await page.locator(".project-overview-grid button").filter({ hasText: "Data" }).click();
  const error = page.getByRole("alert");
  await expect(error).toContainText("Could not verify persisted dataset state");
  await expect(error).toContainText("dataset state temporarily unavailable");
  await expect(page.getByLabel("CSV data")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Inspect dataset", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Confirm dataset contract", exact: true })).toBeDisabled();
  await expect(page.getByText(/This CSV is an editable draft only/)).toHaveCount(0);
  await error.getByRole("button", { name: "Retry dataset check", exact: true }).click();
  await expect(page.getByText(/This CSV is an editable draft only/)).toBeVisible();
  await expect(page.getByLabel("CSV data")).toBeEnabled();
  await expect(page.getByRole("button", { name: "Inspect dataset", exact: true })).toBeEnabled();
  expect(datasetReads).toBe(2);
});

test("E2E-02c pauses training while saved split provenance is unavailable and recovers on retry", async ({ page }) => {
  let splitReads = 0;
  await page.route("**/api/projects/*/dataset/splits", async (route) => {
    splitReads += 1;
    if (splitReads === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved split state temporarily unavailable" }) });
    }
    return route.continue();
  });
  await createProject(page, projectPath("split-state-retry"), "Split state recovery");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  const error = page.getByRole("alert").filter({ hasText: "Saved split provenance is unavailable" });
  await expect(error).toContainText("saved split state temporarily unavailable");
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Freeze .* SplitContract/ })).toBeDisabled();
  await error.getByRole("button", { name: "Retry saved split check", exact: true }).click();
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: /Freeze .* SplitContract/ })).toBeEnabled();
  expect(splitReads).toBe(2);
});

test("E2E-02d does not show an empty-project quick start when saved model context is unavailable", async ({ page }) => {
  let fisReads = 0;
  let trainingReads = 0;
  await page.route("**/api/projects/*/fis/active", async (route) => {
    fisReads += 1;
    if (fisReads === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "active FIS lookup unavailable" }) });
    return route.continue();
  });
  await page.route("**/api/projects/*/training/latest", async (route) => {
    trainingReads += 1;
    if (trainingReads === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "latest run lookup unavailable" }) });
    return route.continue();
  });
  await createProject(page, projectPath("overview-context-retry"), "Overview context recovery");
  const error = page.getByRole("alert");
  await expect(error).toContainText("Could not verify saved model or training context");
  await expect(error).toContainText(/active FIS lookup unavailable|latest run lookup unavailable/);
  await expect(page.getByRole("region", { name: "Optional quick start" })).toHaveCount(0);
  await error.getByRole("button", { name: "Retry project context check", exact: true }).click();
  await expect(page.getByRole("region", { name: "Optional quick start" })).toBeVisible();
  expect(fisReads).toBe(2);
  expect(trainingReads).toBe(2);
});

test("E2E-02e shows and retries an unavailable project integrity check", async ({ page }) => {
  let integrityReads = 0;
  await page.route("**/api/projects/*/integrity", async (route) => {
    integrityReads += 1;
    if (integrityReads === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "integrity index temporarily unavailable" }) });
    return route.continue();
  });
  await createProject(page, projectPath("integrity-retry"), "Integrity recovery");
  const error = page.getByRole("alert").filter({ hasText: "Project integrity is unavailable" });
  await expect(error).toContainText("integrity index temporarily unavailable");
  await expect(page.getByTestId("project-integrity")).toHaveCount(0);
  await error.getByRole("button", { name: "Retry integrity check", exact: true }).click();
  await expect(page.getByTestId("project-integrity")).toBeVisible();
  expect(integrityReads).toBe(2);
});

test("E2E-03 read-only opening disables mutating Studio controls", async ({ page }) => {
  const path = projectPath("readonly");
  await createProject(page, path, "Read only");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByLabel("Read-only").check();
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await expect(page.getByText(/saved data and evidence can be inspected, but dataset imports and contract changes are disabled/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Update description", exact: true })).toBeDisabled();
});

test("E2E-04 future schema reports a controlled error", async ({ page }) => {
  const path = projectPath("future");
  await mkdir(path, { recursive: true });
  await writeFile(join(path, "project.yaml"), "schema_version: 999\n", "utf8");
  await page.goto("/");
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.locator(".error")).toContainText("newer than supported version");
  await expect(page.locator(".project-identity")).toHaveText("No project open");
});

test("E2E-05 backend unavailability is a controlled UI error", async ({ page }) => {
  await page.route("**/api/health", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator(".error")).toBeVisible();
  await expect(page.getByText("Create or open a RuFLEX project", { exact: true })).toBeVisible();
});

test("E2E-06 Studio starts without a Streamlit execution path", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Backend connected", { exact: true })).toBeVisible();
  await expect(page.getByText("RuFLEX Studio", { exact: true })).toBeVisible();
});

test("E2E-07 persists a content-addressed artifact and restores its Studio inventory", async ({ page }) => {
  const path = projectPath("artifact");
  await createProject(page, path, "Artifact project");
  const response = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  const opened = await response.json();
  const ingested = await page.request.post("http://127.0.0.1:8010/api/projects/artifacts/text", { data: { session_id: opened.session_id, text: "persisted studio evidence" } });
  expect(ingested.status()).toBe(201);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByText(/^[0-9a-f]{12} · 25 B · generated$/)).toBeVisible();
});

test("E2E-08 confirms a dataset contract in Data workspace and preserves it across reopen", async ({ page }) => {
  const path = projectPath("dataset");
  await createProject(page, path, "Dataset project");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await expect(page.getByText(/Rows: 3/)).toBeVisible();
  await expect(page.getByText("Role proposals are advisory: choose target and ID columns before freezing the authoritative DatasetContract.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("ID columns")).toHaveValue("entity_id");
  await page.getByLabel("ID columns").fill("");
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await expect(page.getByText(/Contract: target/)).toBeVisible();
  await expect(page.getByText(/Row identity: dataset-fingerprint\/source-row\/v1/)).toBeVisible();
  const frozenRoles = page.getByLabel("Frozen dataset roles");
  await expect(frozenRoles.locator("summary")).toContainText("3 model features · 0 IDs excluded");
  await frozenRoles.locator("summary").click();
  await expect(frozenRoles).toContainText("Model features: entity_id, temperature, torque");
  await expect(frozenRoles).toContainText("Excluded IDs: none");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(path);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await page.getByRole("button", { name: "P", exact: true }).click();
  const persistedDatasetTile = page.locator(".project-overview-grid button").filter({ hasText: "3 rows" });
  await expect(persistedDatasetTile).toContainText("Data");
  await expect(page.getByRole("region", { name: "Optional quick start" })).toHaveCount(0);
  const trainingRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && /\/api\/projects\/training\/(?:run|study-jobs)(?:\/|$)/.test(request.url())) {
      trainingRequests.push(request.url());
    }
  });
  const optionalTraining = page.getByRole("region", { name: "Optional next step" });
  await expect(optionalTraining).toContainText("Your dataset is ready for a model fit");
  await expect(optionalTraining).toContainText("Nothing runs until you choose “Run real training”");
  await expect(optionalTraining).toContainText("held-out test split stays locked");
  await page.route("**/api/models", (route) => route.fulfill({ status: 503, body: "model catalog unavailable" }));
  await optionalTraining.getByRole("button", { name: "Open Training", exact: true }).click();
  await expect(page.locator(".training-workspace")).toBeVisible();
  await expect(page.getByRole("region", { name: "Training choices" })).toContainText("creates one fitted TrainingRun");
  await expect(page.getByRole("region", { name: "Training choices" })).toContainText("preserves the per-seed results as a TrainingStudy");
  await expect(page.getByRole("region", { name: "Training choices" })).toContainText("does not start computation or unlock the test split");
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeVisible();
  expect(trainingRequests).toEqual([]);
  const retry = page.getByRole("button", { name: "Retry model check", exact: true });
  await retry.click();
  await expect(page.getByRole("alert")).toContainText("Could not check available models");
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeDisabled();
  await page.unroute("**/api/models");
  await page.route("**/api/models", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.getByRole("button", { name: "Retry model check", exact: true }).click();
  await expect(page.getByText("No compatible model is available.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run real training", exact: true })).toBeDisabled();
  await page.unroute("**/api/models");
  expect(trainingRequests).toEqual([]);
  await page.locator(".project-object-tree .object-tree-item").filter({ hasText: "target" }).first().click();
  await expect(page.locator(".data-workspace")).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  const reopened = await page.request.post("http://127.0.0.1:8010/api/projects/open", { data: { path } });
  expect(reopened.status()).toBe(200);
  const persisted = await page.request.get(`http://127.0.0.1:8010/api/projects/${(await reopened.json()).session_id}/artifacts`);
  expect(persisted.status()).toBe(200);
});

test("E2E-09 declares and freezes the new-entity generalization contract", async ({ page }) => {
  await createProject(page, projectPath("generalization"), "Generalization project");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "Declare generalization contract", exact: true }).click();
  await expect(page.getByText("Split recommendation: group · Ready to freeze", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Freeze evaluation contract", exact: true }).click();
  await expect(page.getByText("Split recommendation: group · Frozen", { exact: true })).toBeVisible();

  let releasePreview!: () => void;
  let markPreviewStarted!: () => void;
  let markPreviewCompleted!: () => void;
  const previewGate = new Promise<void>((resolve) => { releasePreview = resolve; });
  const previewStarted = new Promise<void>((resolve) => { markPreviewStarted = resolve; });
  const previewCompleted = new Promise<void>((resolve) => { markPreviewCompleted = resolve; });
  let classificationRequests = 0;
  await page.route("**/api/projects/generalization/contracts/*/classify", async (route) => {
    classificationRequests += 1;
    if (classificationRequests === 1) {
      markPreviewStarted();
      await previewGate;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ disposition: "ALLOW", reasons: ["older preview result"] }) });
      markPreviewCompleted();
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ disposition: "BLOCK", reasons: ["newer candidate result"] }) });
  });
  await page.getByRole("button", { name: "Check first preview row", exact: true }).click();
  await previewStarted;
  await page.getByPlaceholder("north or external-lab").fill("unseen-site");
  await page.getByRole("button", { name: "Check candidate scope", exact: true }).click();
  await expect(page.getByText("newer candidate result", { exact: true })).toBeVisible();
  try {
    releasePreview();
    await previewCompleted;
    await expect(page.getByText("older preview result", { exact: true })).toHaveCount(0);
    await expect(page.getByText("newer candidate result", { exact: true })).toBeVisible();
  } finally {
    releasePreview();
  }
  expect(classificationRequests).toBe(2);
});

test("E2E-10 distinguishes unavailable saved training history from an empty project and retries", async ({ page }) => {
  let runListRequests = 0;
  let studyRequests = 0;
  let studyJobRequests = 0;
  await page.route("**/api/projects/*/training/studies/latest", async (route) => {
    studyRequests += 1;
    if (studyRequests === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved Study temporarily unavailable" }) });
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No saved TrainingStudy exists." }) });
  });
  await page.route("**/api/projects/*/training/study-jobs", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    studyJobRequests += 1;
    if (studyJobRequests === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "saved Study jobs temporarily unavailable" }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/projects/*/training/runs", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    runListRequests += 1;
    if (runListRequests === 1) {
      return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "training history temporarily unavailable" }) });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await createProject(page, projectPath("run-history"), "Run history project");
  await page.getByRole("button", { name: /Data.*No dataset/ }).click();
  await page.getByRole("button", { name: "Inspect dataset", exact: true }).click();
  await page.getByRole("button", { name: "Confirm dataset contract", exact: true }).click();
  await page.getByRole("button", { name: "S", exact: true }).click();
  const studyError = page.getByRole("alert").filter({ hasText: "Could not restore saved TrainingStudy" });
  await expect(studyError).toContainText("saved Study temporarily unavailable");
  await expect(page.getByRole("button", { name: "Run multi-seed study", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Retry Study check", exact: true }).click();
  await expect(page.getByText("No saved TrainingStudy exists for this project yet", { exact: false })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Could not restore saved Study jobs" })).toBeVisible();
  await page.getByRole("button", { name: "Retry Study jobs", exact: true }).click();
  await expect(page.getByRole("button", { name: "Run multi-seed study", exact: true })).toBeEnabled();
  expect(studyRequests).toBe(2);
  expect(studyJobRequests).toBe(2);
  await page.getByRole("button", { name: "A", exact: true }).click();
  const error = page.getByRole("alert");
  await expect(error).toContainText("Could not restore saved training runs");
  await expect(error).toContainText("training history temporarily unavailable");
  await expect(page.getByText("No trained run", { exact: true })).toHaveCount(0);
  await error.getByRole("button", { name: "Retry loading saved runs" }).click();
  await expect(page.getByText("No trained run", { exact: true })).toBeVisible();
  expect(runListRequests).toBe(2);
});

test("E2E-11 distinguishes unavailable lineage from a genuinely empty graph and retries", async ({ page }) => {
  let lineageRequests = 0;
  await page.route("**/api/projects/*/lineage", async (route) => {
    lineageRequests += 1;
    if (lineageRequests === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "lineage store temporarily unavailable" }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ schema_version: 1, nodes: [], edges: [], scientific_note: "No persisted objects yet." }) });
  });
  await createProject(page, projectPath("lineage-retry"), "Lineage recovery project");
  const panel = page.locator(".project-lineage-panel");
  await expect(panel.getByRole("alert")).toContainText("Could not load persisted project lineage");
  await expect(panel.getByRole("alert")).toContainText("lineage store temporarily unavailable");
  await expect(panel.getByText("Lineage will appear as persisted datasets, runs, analyses and evidence are created.", { exact: true })).toHaveCount(0);
  await panel.getByRole("button", { name: "Retry lineage" }).click();
  await expect(panel.getByText("Lineage will appear as persisted datasets, runs, analyses and evidence are created.", { exact: true })).toBeVisible();
  expect(lineageRequests).toBe(2);
});
