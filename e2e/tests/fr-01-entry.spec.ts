import { test, expect } from "@playwright/test";
import { DEMO_ENTRY_CODE, enterViaCorporateLink, resumeBundle } from "./support/participant";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

test.describe("FR-01 Вход участника по QR/ссылке, создание токена", () => {
  test("FR-01.1 переход по корпоративной ссылке создаёт сессию и выдаёт участнику токен", async ({ page }) => {
    await enterViaCorporateLink(page);
    await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();
    // Токен создан и сохранён в localStorage — это то, чем система связывает вход и итог (ТЗ п.3).
    const token = await page.evaluate(() => window.localStorage.getItem("pez_participant_token"));
    expect(token).toBeTruthy();
  });

  test("FR-01.2 участник может увидеть и сохранить свой токен (код/QR)", async ({ page }) => {
    await enterViaCorporateLink(page);
    const token = await page.evaluate(() => window.localStorage.getItem("pez_participant_token"));
    await expect(page.locator(".token-box code")).toHaveText(token ?? "");
  });

  test("FR-01.3 повторное открытие ссылки с сохранённым токеном продолжает прежнюю сессию", async ({ page }) => {
    await enterViaCorporateLink(page);
    const token = await page.evaluate(() => window.localStorage.getItem("pez_participant_token"));

    await page.reload();
    await resumeBundle(page);
    await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();
    const tokenAfterReload = await page.evaluate(() => window.localStorage.getItem("pez_participant_token"));
    expect(tokenAfterReload).toBe(token);
  });

  test("FR-01.4 неверная или отключённая ссылка показывает понятную ошибку и не создаёт токен", async ({ page }) => {
    // Не используем enterViaCorporateLink — он ждёт экран Welcome, а здесь код заведомо невалиден.
    await page.goto("/?code=does-not-exist");
    await expect(page.getByRole("heading", { name: "Ссылка недействительна или отключена" })).toBeVisible();
    const token = await page.evaluate(() => window.localStorage.getItem("pez_participant_token"));
    expect(token).toBeNull();
  });

  test("FR-01.5 вход не запрашивает ФИО, телефон, e-mail и табельный номер", async ({ page }) => {
    await enterViaCorporateLink(page);
    const identifierFields = page.locator(
      ['input[type="email"]', 'input[type="tel"]', '[autocomplete~="name"]', '[autocomplete="email"]', '[autocomplete="tel"]'].join(
        ", ",
      ),
    );
    await expect(identifierFields).toHaveCount(0);
  });

  test("API-01.1 создание сессии с неизвестным кодом не создаёт токен на бэкенде", async ({ request }) => {
    const response = await request.post(`${API_URL}/participant/sessions/`, {
      data: { entry_code: "definitely-not-a-real-code" },
    });
    expect(response.status()).toBe(404);
  });

  test("API-01.2 создание сессии с валидным кодом возвращает новый уникальный токен", async ({ request }) => {
    const first = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
    const second = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
    expect(first.status()).toBe(201);
    expect(second.status()).toBe(201);
    const firstBody = await first.json();
    const secondBody = await second.json();
    expect(firstBody.token).not.toBe(secondBody.token);
  });
});
