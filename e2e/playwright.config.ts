import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const legacy = process.env.E2E_SUITE === "legacy";
const testMatch = legacy
  ? /fr-(0[2-8]|09|1[0-3])-.*\.spec\.ts/
  : /(?:api|smoke|fr-(?:01|14|15|16)-[^/]+)\.spec\.ts/;

// Участник — mobile-first, employer/PRODEX — desktop-first (см. ТЗ, раздел 5).
// Поэтому контуры employer/PRODEX/RBAC и API-проверки в mobile не гоняем.
const desktopOnly = [/fr-(09|10|11|12|16)-.*\.spec\.ts/, /api\.spec\.ts/];

export default defineConfig({
  testDir: "./tests",
  testMatch,
  timeout: 90_000,
  workers: process.env.CI ? 2 : undefined,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    locale: "ru-RU",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testIgnore: desktopOnly },
  ],
});
