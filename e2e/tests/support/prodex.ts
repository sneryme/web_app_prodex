import { expect, type Page } from "@playwright/test";
import { DEMO_STAFF_PASSWORD, ORG_ADMIN_USERNAME, PRODEX_ADMIN_USERNAME } from "./employer";

// Логин общий с employer-контуром (одна и та же identity.StaffProfile/DRF TokenAuthentication),
// но экран и сессия отдельные (ТЗ FR-11.6) — отсюда отдельный helper, а не переиспользование
// loginAsEmployer.
export async function loginAsProdexAdmin(
  page: Page,
  username: string = PRODEX_ADMIN_USERNAME,
  password: string = DEMO_STAFF_PASSWORD,
) {
  await page.goto("/prodex");
  await page.getByLabel("Логин").fill(username);
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти" }).click();
}

export { ORG_ADMIN_USERNAME, PRODEX_ADMIN_USERNAME, DEMO_STAFF_PASSWORD };
