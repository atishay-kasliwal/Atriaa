import { defineConfig } from "@playwright/test";

const port = Number(process.env.ATRIA_TEST_PORT || 8791);

export default defineConfig({
  testDir: "./test/browser",
  workers: 1,
  use: {
    baseURL: `http://localhost:${port}`,
    browserName: "chromium",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  },
  webServer: {
    command: `npm run db:local && npx wrangler dev --port ${port}`,
    url: `http://localhost:${port}/api/health`,
    reuseExistingServer: !process.env.CI,
  },
});
