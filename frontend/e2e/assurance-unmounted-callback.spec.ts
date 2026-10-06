import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-assurance-unmounted-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

test("a persisted AssuranceCase response from a closed project cannot hydrate the next project", async ({ page }) => {
  test.setTimeout(25_000);
  const sourcePath = projectPath("source");
  const nextPath = projectPath("next");
  const nextCreated = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path: nextPath, name: "Next assurance-free project" } });
  expect(nextCreated.status()).toBe(201);

  let releaseAssurance!: () => void;
  let markAssurancePersisted!: () => void;
  const assuranceGate = new Promise<void>((resolve) => { releaseAssurance = resolve; });
  const assurancePersisted = new Promise<void>((resolve) => { markAssurancePersisted = resolve; });
  let assuranceStarted = false;
  let persistedAssuranceId = "";
  await page.route("**/api/projects/evidence/assurance-jobs", async (route) => {
    if (route.request().method() === "POST") assuranceStarted = true;
    await route.continue();
  });
  await page.route("**/api/projects/*/evidence/assurance-cases/*", async (route) => {
    if (!assuranceStarted) return route.continue();
    const response = await route.fetch();
    if (!response.ok()) return route.fulfill({ response });
    const payload = await response.json() as { assurance_id: string };
    persistedAssuranceId = payload.assurance_id;
    markAssurancePersisted();
    await assuranceGate;
    await route.fulfill({ response });
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(sourcePath);
  await page.getByLabel("Project name").fill("Assurance source project");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByTitle("EVIDENCE").click();
  await page.getByRole("button", { name: "Build AssuranceCase", exact: true }).click();
  await assurancePersisted;

  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByLabel("Project path").fill(nextPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Next assurance-free project", exact: true })).toBeVisible();
  await page.getByTitle("EVIDENCE").click();

  try {
    const assuranceResponse = page.waitForResponse((response) =>
      response.url().includes("/evidence/assurance-cases/") && response.request().method() === "GET" && response.status() === 200,
    );
    releaseAssurance();
    await assuranceResponse;
    expect(persistedAssuranceId).toBeTruthy();
    await expect(page.getByTestId("assurance-empty")).toBeVisible();
    await expect(page.getByTestId("assurance-case")).toHaveCount(0);
    await expect(page.locator(".project-object-tree")).not.toContainText(persistedAssuranceId.slice(0, 8));
  } finally {
    releaseAssurance();
  }
});
