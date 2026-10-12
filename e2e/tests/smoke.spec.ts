import { test, expect } from "@playwright/test";
import { hasHorizontalOverflow } from "./support/layout";

// Что реально есть в scaffold: стартовая страница участника (frontend/src/main.tsx).
// Здесь же охранные проверки правил проекта, которые должны держаться на любом экране.

test.describe("стартовая страница участника", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("SMOKE-01 показывает заголовок и кнопку начала маршрута", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Комната психоэмоционального здоровья",
    );
    await expect(page.getByRole("button", { name: "Начать знакомство" })).toBeVisible();
  });

  test("SMOKE-02 показывает дисклеймер: результаты не являются диагнозом", async ({ page }) => {
    await expect(page.getByText("не являются диагнозом")).toBeVisible();
  });

  test("SMOKE-03 страница не выходит за ширину экрана (mobile-first)", async ({ page }) => {
    expect(await hasHorizontalOverflow(page)).toBe(false);
  });

  test("SMOKE-04 не запрашивает прямые идентификаторы (ФИО, телефон, e-mail)", async ({ page }) => {
    const identifierFields = page.locator(
      [
        'input[type="email"]',
        'input[type="tel"]',
        '[autocomplete~="name"]',
        '[autocomplete="email"]',
        '[autocomplete="tel"]',
      ].join(", "),
    );
    await expect(identifierFields).toHaveCount(0);
  });

  test("SMOKE-05 не использует запрещённые формулировки", async ({ page }) => {
    // «клиническая» воспринимается как диагноз; общий индекс здоровья запрещён (PROJECT_RULES №2).
    const text = await page.locator("body").innerText();
    expect(text).not.toMatch(/клиническ|общий индекс|индекс здоровья/i);
  });
});
