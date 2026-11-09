import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end and accessibility tests. They run against an already started stack (the compose
 * file with the demo profile), never against a dev server, so they exercise the real proxy,
 * headers, API and database.
 *
 * The development certificate is self-signed, so certificate errors are ignored here and
 * nowhere else.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  // One worker: the proxy rate-limits sign-in, registration and profile writes per address
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "https://localhost:8443",
    ignoreHTTPSErrors: true,
    locale: "uk-UA",
    trace: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
