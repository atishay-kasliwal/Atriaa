import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "../..");
const python = existsSync(path.join(root, ".venv/bin/python")) ? path.join(root, ".venv/bin/python") : "python3";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4410",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn --app-dir backend main:app --host 127.0.0.1 --port 8801`,
      cwd: root,
      url: "http://127.0.0.1:8801/health",
      reuseExistingServer: !process.env.CI,
      env: { ATRIA_STORE: "memory", TIGER_DATABASE_URL: "", GEMINI_API_KEY: "", SUPABASE_URL: "", SUPABASE_SERVICE_ROLE_KEY: "", SENTRY_DSN: "" },
    },
    {
      command: "npm run build && npm run start -- --hostname 127.0.0.1 --port 4410",
      url: "http://127.0.0.1:4410",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { ATRIA_API_URL: "http://127.0.0.1:8801" },
    },
  ],
});
