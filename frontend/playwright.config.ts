import { existsSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, "..");
const pythonCandidates = [
  process.env.RUFLEX_PYTHON,
  resolve(repoRoot, ".venv/bin/python"),
  resolve(repoRoot, "../venv/bin/python"),
].filter((candidate): candidate is string => Boolean(candidate));
const python = pythonCandidates.find((candidate) => existsSync(candidate)) ?? "python3";

// Keep the Playwright-managed browser revision next to the worktree unless the
// caller deliberately supplies another cache. This avoids stale global browser
// caches without hard-coding one developer's absolute repository path.
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(repoRoot, ".playwright-browsers");

function localChromiumExecutable(): string | undefined {
  const browserRoot = process.env.PLAYWRIGHT_BROWSERS_PATH!;
  if (!existsSync(browserRoot)) return undefined;
  const chromiumDirectory = readdirSync(browserRoot)
    .filter((entry) => entry.startsWith("chromium-"))
    .sort()
    .at(-1);
  if (!chromiumDirectory) return undefined;
  const executable = join(browserRoot, chromiumDirectory, "chrome-linux64", "chrome");
  return existsSync(executable) ? executable : undefined;
}

// A partially completed `playwright install chromium` can contain Chrome for
// Testing but not the optional headless-shell archive. Use that installed
// Chromium explicitly, while preserving a caller-provided executable override.
const chromiumExecutable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ?? localChromiumExecutable();

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  // The Studio acceptance suite shares one FastAPI/Vite development-server pair.
  // Serial execution keeps the browser checks deterministic: concurrent workers
  // can otherwise starve stateful UI requests and turn an enabled control into a
  // timeout without representing a product defect.
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5174",
    headless: true,
    launchOptions: {
      executablePath: chromiumExecutable,
      args: ["--disable-gpu"],
    },
  },
  webServer: [
    {
      command: `cd .. && PYTHONPATH=src ${python} -m uvicorn ruflex.api.main:app --host 127.0.0.1 --port 8010`,
      url: "http://127.0.0.1:8010/api/health",
      reuseExistingServer: false,
    },
    {
      command: "VITE_RUFLEX_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
  ],
});
