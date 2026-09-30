import { test, expect } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

test("API-01 health отвечает ok", async ({ request }) => {
  const response = await request.get(`${API_URL}/health/`);
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok", service: "pez-digital-api" });
});
