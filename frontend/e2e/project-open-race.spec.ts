import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-project-open-race-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

test("a late earlier project-open response cannot replace the newer project", async ({ page }) => {
  test.setTimeout(20_000);
  const firstPath = projectPath("first");
  const secondPath = projectPath("second");
  for (const [path, name] of [[firstPath, "First project"], [secondPath, "Second project"]]) {
    const created = await page.request.post("http://127.0.0.1:8010/api/projects", { data: { path, name } });
    expect(created.status()).toBe(201);
  }

  let releaseFirstOpen!: () => void;
  let markFirstOpenStarted!: () => void;
  const firstOpenGate = new Promise<void>((resolve) => { releaseFirstOpen = resolve; });
  const firstOpenStarted = new Promise<void>((resolve) => { markFirstOpenStarted = resolve; });
  let staleSessionId = "";
  let closedSessionId = "";
  await page.route("**/api/projects/open", async (route) => {
    const body = route.request().postDataJSON() as { path?: string };
    if (body.path === firstPath) {
      const response = await route.fetch();
      staleSessionId = (await response.json() as { session_id: string }).session_id;
      markFirstOpenStarted();
      await firstOpenGate;
      return route.fulfill({ response });
    }
    await route.continue();
  });
  await page.route("**/api/projects/close", async (route) => {
    const body = route.request().postDataJSON() as { session_id?: string };
    if (body.session_id === staleSessionId) closedSessionId = body.session_id;
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(firstPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await firstOpenStarted;
  await page.getByLabel("Project path").fill(secondPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Second project", exact: true })).toBeVisible();

  try {
    const staleSessionClose = page.waitForResponse((response) =>
      response.url().endsWith("/api/projects/close")
      && response.request().method() === "POST"
      && (response.request().postDataJSON() as { session_id?: string }).session_id === staleSessionId,
    );
    const firstResponse = page.waitForResponse((response) => {
      const request = response.request();
      return response.url().endsWith("/api/projects/open")
        && request.method() === "POST"
        && (request.postDataJSON() as { path?: string }).path === firstPath;
    });
    releaseFirstOpen();
    await firstResponse;
    await staleSessionClose;
    expect(staleSessionId).toBeTruthy();
    expect(closedSessionId).toBe(staleSessionId);
    await expect(page.getByRole("heading", { name: "Second project", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "First project", exact: true })).toHaveCount(0);
  } finally {
    releaseFirstOpen();
  }
});
