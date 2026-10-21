import { expect, test } from "@playwright/test";
import { DEMO_STAFF_PASSWORD, ORG_ADMIN_USERNAME, loginAsEmployer, PRODEX_ADMIN_USERNAME } from "./support/employer";

// Тестовые данные: `manage.py seed_employer_demo_streams` — демо-организация/"2026-H2" (8
// участников, выше порога публикации 5) и "ООО Вектор Плюс"/"2026-pilot" (3 участника, ниже
// порога) — специально заведены, чтобы показать и обычный, и подавленный (suppressed) случаи.
// Учётки сотрудников — `manage.py seed_demo_staff` (ТЗ FR-09.1/FR-12-lite).

/** selectOption({label}) матчит только точную строку — а в лейбле ещё и participant_count,
 * который может отличаться при повторном прогоне сида. Ищем нужный <option> по подстроке кода
 * потока и селектим по его value, а не по всему видимому тексту. */
async function selectStreamByCode(page: import("@playwright/test").Page, code: string) {
  const select = page.getByLabel("Поток");
  await expect(select).toBeEnabled(); // пока стримы не загрузились, селект disabled (см. EmployerApp.tsx)

  let value: string | null = null;
  await expect(async () => {
    const options = select.locator("option");
    const count = await options.count();
    for (let i = 0; i < count; i += 1) {
      const text = await options.nth(i).innerText();
      if (text.includes(code)) {
        value = await options.nth(i).getAttribute("value");
        return;
      }
    }
    throw new Error(`Поток с кодом "${code}" пока не найден в списке`);
  }).toPass();

  await select.selectOption(value!);
}

test.describe("FR-09 Employer dashboard", () => {
  test("FR-09.1 аноним видит экран входа, дашборд доступен только после логина сотрудника", async ({ page }) => {
    await page.goto("/employer");
    // Аноним не видит ни организаций, ни агрегатов — только форму входа.
    await expect(page.getByRole("heading", { name: "Вход для администратора" })).toBeVisible();
    await expect(page.locator(".employer-filters")).toHaveCount(0);

    await page.getByLabel("Логин").fill(ORG_ADMIN_USERNAME);
    await page.getByLabel("Пароль").fill("неверный-пароль");
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.locator(".employer-error")).toContainText("Неверный логин или пароль");

    await page.getByLabel("Пароль").fill(DEMO_STAFF_PASSWORD);
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.locator(".employer-filters")).toBeVisible();
    // Роль и организация видны в шапке; org_admin привязан к одной организации (ORG_SCOPED_ROLES),
    // поэтому в выпадающем списке у него ровно одна запись.
    await expect(page.locator(".employer-session__info")).toContainText("Администратор организации");
    await expect(page.getByLabel("Организация").locator("option")).toHaveCount(1);
  });

  test("FR-09.2 видны охват, completion, 5 групповых показателей, распределения и сравнение «вход / итог»", async ({
    page,
  }) => {
    await loginAsEmployer(page);
    await expect(page.locator(".employer-stat__label")).toHaveCount(3); // охват + 2×completion
    await expect(page.locator(".employer-card")).toHaveCount(5); // 5 отчётных показателей

    const firstCard = page.locator(".employer-card").first();
    // В группе по умолчанию (demo-stream, 321+ участников) показатели не подавлены — есть среднее
    // и распределение по зонам у обоих этапов, плюс сводка по тренду.
    await expect(firstCard.locator(".employer-mean")).toHaveCount(2);
    await expect(firstCard.locator(".employer-distribution li").first()).toBeVisible();
    await expect(firstCard.locator(".employer-card__trend")).toContainText("Улучшение");
    await expect(firstCard.locator(".employer-card__trend")).toContainText("Ухудшение");
  });

  test("FR-09.3 фильтр по потоку меняет отображаемые данные", async ({ page }) => {
    await loginAsEmployer(page);
    const streamSelect = page.getByLabel("Поток");
    await expect(streamSelect).toBeVisible();

    const meanBefore = await page.locator(".employer-mean").first().innerText();

    await selectStreamByCode(page, "2026-H2");
    await expect(async () => {
      const meanAfter = await page.locator(".employer-mean").first().innerText();
      expect(meanAfter).not.toBe(meanBefore);
    }).toPass();

    // Охват тоже должен поменяться — в 2026-H2 ровно 8 участников (сид-команда).
    await expect(page.locator(".employer-stat__value").first()).toHaveText("8");
  });

  test("FR-09.4 группа меньше порога публикации скрыта", async ({ page }) => {
    await loginAsEmployer(page, PRODEX_ADMIN_USERNAME); // нужен доступ к обеим организациям
    await page.getByLabel("Организация").selectOption({ label: "ООО Вектор Плюс" });
    await selectStreamByCode(page, "2026-pilot");

    await expect(page.locator(".employer-stat__value").first()).toHaveText("3"); // охват виден
    // А вот по каждому показателю — только пометка о скрытии, не среднее/распределение.
    await expect(page.locator(".employer-suppressed").first()).toContainText("слишком мала");
    await expect(page.locator(".employer-mean")).toHaveCount(0);
    await expect(page.locator(".employer-distribution li")).toHaveCount(0);
  });

  test("FR-09.5 в интерфейсе и ответах API нет индивидуальных строк, токенов и ответов", async ({ page, request }) => {
    await loginAsEmployer(page);
    await expect(page.locator(".employer-card")).toHaveCount(5);

    const bodyText = await page.locator("body").innerText();
    // Токен участника — 32+ символов url-safe base64; такого на дашборде быть не должно.
    expect(bodyText).not.toMatch(/[A-Za-z0-9_-]{32,}/);

    const apiUrl = process.env.E2E_API_URL ?? "http://localhost:8000/api";
    const loginResponse = await request.post(`${apiUrl}/identity/login/`, {
      data: { username: PRODEX_ADMIN_USERNAME, password: DEMO_STAFF_PASSWORD },
    });
    const { token } = await loginResponse.json();

    const response = await request.get(`${apiUrl}/employer/organizations/1/overview/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const payload = await response.json();
    const serialized = JSON.stringify(payload);
    for (const forbidden of ["token", "selected_option", "raw_value", "question_id"]) {
      expect(serialized).not.toContain(forbidden);
    }
  });
});
