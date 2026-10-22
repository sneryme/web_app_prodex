import { expect, test } from "@playwright/test";
import { DEMO_STAFF_PASSWORD, ORG_ADMIN_USERNAME, PRODEX_ADMIN_USERNAME, loginAsProdexAdmin } from "./support/prodex";

// Тестовые данные: `manage.py seed_demo_licenses` (активная лицензия у демо-организации,
// истёкшая у «ООО Вектор Плюс»), `manage.py seed_employer_demo_streams` (потоки/участники) и
// `manage.py seed_demo_staff` (учётки) — см. README.md.

test.describe("FR-11 PRODEX Admin dashboard", () => {
  test("FR-11.1 аноним видит экран входа; администратор организации получает отказ, а не данные", async ({
    page,
  }) => {
    await page.goto("/prodex");
    await expect(page.getByRole("heading", { name: "Вход администратора PRODEX" })).toBeVisible();
    await expect(page.locator(".prodex-table")).toHaveCount(0);

    await loginAsProdexAdmin(page, ORG_ADMIN_USERNAME, DEMO_STAFF_PASSWORD);
    await expect(page.getByRole("heading", { name: "Доступ запрещён" })).toBeVisible();
    await expect(page.locator(".prodex-table")).toHaveCount(0);
  });

  test("FR-11.2/FR-11.3 таблица клиентов со статусами лицензии, фильтр по названию работает", async ({ page }) => {
    await loginAsProdexAdmin(page);
    await expect(page.getByRole("heading", { name: "Операционный контур PRODEX" })).toBeVisible();

    const clientsTable = page.locator(".prodex-table").first();
    await expect(clientsTable.locator("tbody tr")).toHaveCount(2); // демо-организация + ООО Вектор Плюс
    await expect(clientsTable).toContainText("Активна");
    await expect(clientsTable).toContainText("срок истёк");

    await page.getByLabel("Поиск").fill("Вектор");
    await expect(clientsTable.locator("tbody tr")).toHaveCount(1);
    await expect(clientsTable).toContainText("ООО Вектор Плюс");
  });

  test("FR-11.4 видны потоки, completion, активность и ошибки как технические метрики", async ({ page }) => {
    await loginAsProdexAdmin(page);

    await expect(page.locator(".prodex-stat__label")).toHaveCount(6);
    const stats = page.locator(".prodex-stat");
    await expect(stats.filter({ hasText: "Организаций" }).locator(".prodex-stat__value")).toHaveText("2");
    await expect(stats.filter({ hasText: "Ошибки подсчёта" })).toBeVisible();
  });

  test("FR-11.5 ни в интерфейсе, ни в ответе API нет психологических показателей участников", async ({
    page,
    request,
  }) => {
    await loginAsProdexAdmin(page);
    await expect(page.locator(".prodex-table")).toHaveCount(2);

    const bodyText = await page.locator("body").innerText();
    for (const forbidden of ["hads_", "eq5d_", "situational_anxiety", "trait_anxiety", "клиническ"]) {
      expect(bodyText.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }

    const apiUrl = process.env.E2E_API_URL ?? "http://localhost:8000/api";
    const loginResponse = await request.post(`${apiUrl}/identity/login/`, {
      data: { username: PRODEX_ADMIN_USERNAME, password: DEMO_STAFF_PASSWORD },
    });
    const { token } = await loginResponse.json();
    const response = await request.get(`${apiUrl}/prodex/operations/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const serialized = JSON.stringify(await response.json());
    for (const forbidden of ["indicator_code", "zone", "raw_score", "token"]) {
      expect(serialized).not.toContain(forbidden);
    }
  });

  test("FR-11.6 интерфейс PRODEX Admin отделён от дашборда работодателя", async ({ page }) => {
    await loginAsProdexAdmin(page);
    // Своя шапка/заголовок и класс-неймспейс, не employer-*.
    await expect(page.getByRole("heading", { name: "Операционный контур PRODEX" })).toBeVisible();
    await expect(page.locator(".employer-shell")).toHaveCount(0);
    await expect(page.locator(".employer-filters")).toHaveCount(0);
  });
});
