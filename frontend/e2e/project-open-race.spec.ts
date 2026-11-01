import { expect, test } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

function projectPath(label: string): string {
  return join(tmpdir(), `ruflex-project-open-race-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

test("project open is serialized before switching to another project", async ({ page }) => {
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
  let secondOpenRequests = 0;
  await page.route("**/api/projects/open", async (route) => {
    const body = route.request().postDataJSON() as { path?: string };
    if (body.path === firstPath) {
      const response = await route.fetch();
      markFirstOpenStarted();
      await firstOpenGate;
      return route.fulfill({ response });
    }
    if (body.path === secondPath) secondOpenRequests += 1;
    await route.continue();
  });

  await page.goto("/");
  await page.getByLabel("Project path").fill(firstPath);
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await firstOpenStarted;
  await expect(page.getByRole("button", { name: "Opening project…", exact: true })).toBeDisabled();
  expect(secondOpenRequests).toBe(0);

  try {
    const firstResponse = page.waitForResponse((response) => {
      const request = response.request();
      return response.url().endsWith("/api/projects/open")
        && request.method() === "POST"
        && (request.postDataJSON() as { path?: string }).path === firstPath;
    });
    releaseFirstOpen();
    await firstResponse;
    await expect(page.locator(".project-identity")).toContainText("First project");
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByLabel("Project path").fill(secondPath);
    await page.getByRole("button", { name: "Open project", exact: true }).click();
    await expect(page.locator(".project-identity")).toContainText("Second project");
    await expect(page.locator(".project-identity")).not.toContainText("First project");
    expect(secondOpenRequests).toBe(1);
  } finally {
    releaseFirstOpen();
  }
});
