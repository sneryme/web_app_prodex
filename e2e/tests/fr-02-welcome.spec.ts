import { test, expect } from "@playwright/test";
import { enterViaCorporateLink } from "./support/participant";

test.describe("FR-02 Welcome-экран", () => {
  test("FR-02.1 показывает цель, время прохождения, конфиденциальность и что увидит работодатель", async ({ page }) => {
    await enterViaCorporateLink(page);
    const text = await page.locator(".card").innerText();
    expect(text).toMatch(/цель/i);
    expect(text).toMatch(/минут/i);
    expect(text).toMatch(/конфиденциальность/i);
    expect(text).toMatch(/работодатель/i);
  });

  test("FR-02.2 кнопка «Начать знакомство» ведёт на отдельный экран согласий", async ({ page }) => {
    await enterViaCorporateLink(page);
    await page.getByRole("button", { name: "Начать знакомство" }).click();
    await expect(page.getByRole("heading", { name: "Прежде чем начать" })).toBeVisible();
    await expect(page.getByLabel("Я согласен(на) на обработку персональных данных в рамках тестирования")).toBeVisible();
  });

  test("FR-02.3 текст о работодателе: только агрегаты, индивидуальные результаты не передаются", async ({ page }) => {
    await enterViaCorporateLink(page);
    await expect(page.getByText(/обезличенную групповую статистику/i)).toBeVisible();
  });

  test("FR-02.4 на mobile нет горизонтального скролла, кнопка доступна без прокрутки", async ({ page }, testInfo) => {
    // Проверка по смыслу мобильная — на десктопном 720px-viewport кнопка ожидаемо ниже сгиба без скролла,
    // это не баг. Реальный mobile-viewport берётся из Playwright-проекта "mobile" (playwright.config.ts).
    test.skip(testInfo.project.name !== "mobile", "Проверка актуальна только для мобильного профиля");
    await enterViaCorporateLink(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByRole("button", { name: "Начать знакомство" })).toBeInViewport();
  });
});
