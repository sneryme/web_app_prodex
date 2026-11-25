import { test, expect } from "@playwright/test";
import { answerCurrentQuestion, completeStage, resumeBundle, startTesting } from "./support/participant";
import { hasHorizontalOverflow } from "./support/layout";

test.describe("FR-06 Один вопрос на экран, прогресс, автосохранение", () => {
  test("FR-06.1 на экране ровно один вопрос, варианты ответа — крупные карточки", async ({ page }) => {
    await startTesting(page);
    await expect(page.locator(".card h2")).toHaveCount(1);
    await expect(page.locator(".option-card")).not.toHaveCount(0);
  });

  test("FR-06.2 индикатор прогресса виден и растёт после каждого ответа", async ({ page }) => {
    await startTesting(page);
    const fill = page.locator(".progress-fill");
    // На первом вопросе прогресс — 0%, поэтому у .progress-fill нулевая ширина (Playwright считает его
    // невидимым); видимость проверяем по контейнеру, который всегда имеет ненулевой размер.
    await expect(page.locator(".progress-track")).toBeVisible();
    const widthBefore = await fill.evaluate((el) => (el as HTMLElement).style.width);
    await answerCurrentQuestion(page);
    await expect(async () => {
      const widthAfter = await fill.evaluate((el) => (el as HTMLElement).style.width);
      expect(widthAfter).not.toBe(widthBefore);
    }).toPass();
  });

  test("FR-06.3 перезагрузка страницы возвращает на тот же вопрос с сохранённым ответом", async ({ page }) => {
    await startTesting(page);
    const firstQuestionText = await page.locator(".card h2").innerText();
    await answerCurrentQuestion(page);
    const secondQuestionText = await page.locator(".card h2").innerText();
    expect(secondQuestionText).not.toBe(firstQuestionText);

    await page.reload();
    await resumeBundle(page);
    await expect(page.locator(".card h2")).toHaveText(secondQuestionText);
    // Ответ на первый вопрос никуда не делся — «Назад» показывает выбранную карточку.
    await page.getByRole("button", { name: "Назад" }).click();
    await expect(page.locator(".card h2")).toHaveText(firstQuestionText);
    await expect(page.locator(".option-card.selected")).toHaveCount(1);
  });

  test("FR-06.4 после закрытия браузера участник продолжает с того же места по токену", async ({ browser, baseURL }) => {
    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();
    await startTesting(page);
    await answerCurrentQuestion(page);
    const questionAfterOneAnswer = await page.locator(".card h2").innerText();
    const storageState = await context.storageState();
    await context.close();

    // Переносим cookie в новый контекст, как при повторном открытии браузера.
    const reopenedContext = await browser.newContext({ baseURL, storageState });
    const reopenedPage = await reopenedContext.newPage();
    await reopenedPage.goto("/");
    await resumeBundle(reopenedPage);
    await expect(reopenedPage.locator(".card h2")).toHaveText(questionAfterOneAnswer);
    await reopenedContext.close();
  });

  test("FR-06.5 можно вернуться назад и изменить ответ", async ({ page }) => {
    await startTesting(page);
    const firstOptionLabel = await page.locator(".option-card").nth(0).innerText();
    await page.locator(".option-card").nth(0).click(); // отвечаем на вопрос 1 → автопереход на вопрос 2
    await expect(page.getByText("Вопрос 2 из", { exact: false })).toBeVisible();

    await page.getByRole("button", { name: "Назад" }).click();
    await expect(page.getByText("Вопрос 1 из", { exact: false })).toBeVisible();

    const secondOptionLabel = await page.locator(".option-card").nth(1).innerText();
    expect(secondOptionLabel).not.toBe(firstOptionLabel);
    await page.locator(".option-card").nth(1).click(); // меняем ответ на вопрос 1

    // Правка уже отвеченного вопроса не создаёт дубль-переход — остаёмся на вопросе 1 с новым выбором.
    await expect(page.getByText("Вопрос 1 из", { exact: false })).toBeVisible();
    await expect(page.locator(".option-card.selected")).toHaveText(secondOptionLabel);
  });

  test("FR-06.7 при потере сети ответ не теряется, участник видит понятное сообщение", async ({ page }) => {
    await startTesting(page);
    let intercepted = false;
    await page.route("**/answers/", async (route) => {
      if (!intercepted) {
        intercepted = true;
        await route.abort("failed");
      } else {
        await route.continue();
      }
    });

    await page.locator(".option-card").first().click();
    await expect(page.locator(".error-banner")).toBeVisible();
    await expect(page.locator(".option-card.selected")).toHaveCount(1);

    await page.getByRole("button", { name: "Повторить" }).click();
    await expect(page.locator(".error-banner")).toHaveCount(0);
    await page.unroute("**/answers/");
  });

  test("FR-06.8 на mobile ни один экран вопросов не даёт горизонтального скролла", async ({ page }) => {
    // Реальный mobile-viewport берётся из Playwright-проекта "mobile" (playwright.config.ts);
    // принудительный узкий viewport в desktop-браузере даёт ложный overflow из-за нативного скроллбара Chrome.
    await startTesting(page);
    for (let i = 0; i < 3; i += 1) {
      expect(await hasHorizontalOverflow(page)).toBe(false);
      await answerCurrentQuestion(page);
    }
  });
});
