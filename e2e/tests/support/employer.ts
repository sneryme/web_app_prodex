import { expect, type Page } from "@playwright/test";

// Созданы `manage.py seed_demo_staff` — см. CHANGELOG. Роли по Положению о ролях всего две:
// администратор организации (привязан к своему юрлицу) и администратор PRODEX (не привязан).
// Имена учёток исторические и специально не менялись, чтобы не ломать уже заведённые локальные БД.
export const PRODEX_ADMIN_USERNAME = "prodex_demo"; // prodex_admin — видит все организации
export const ORG_ADMIN_USERNAME = "hr_demo"; // org_admin демо-организации
export const DEMO_STAFF_PASSWORD = "prodex-demo-2026";

export async function loginAsEmployer(
  page: Page,
  username: string = PRODEX_ADMIN_USERNAME,
  password: string = DEMO_STAFF_PASSWORD,
) {
  await page.goto("/employer");
  await page.getByLabel("Логин").fill(username);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.locator(".employer-filters")).toBeVisible();
}
