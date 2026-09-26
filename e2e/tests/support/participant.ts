import { expect, type Page } from "@playwright/test";

// Демо-организация создаётся командой `manage.py seed_demo_organization` (см. README).
export const DEMO_ENTRY_CODE = "demo-entry-code";
// Общее число вопросов в опроснике-заглушке (`manage.py seed_dummy_questionnaire`): 2 на каждую из 3 методик.
export const DUMMY_QUESTIONNAIRE_LENGTH = 6;

// Создание сессии/сохранение согласия — асинхронные запросы к API; каждый хелпер дожидается
// видимого следствия запроса, чтобы тесты не ловили гонку с недорисованным экраном.

export async function enterViaCorporateLink(page: Page, entryCode: string = DEMO_ENTRY_CODE) {
  await page.goto(`/?code=${entryCode}`);
  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();
}

export async function acceptConsent(page: Page) {
  await page.getByRole("button", { name: "Начать знакомство" }).click();
  await page.getByLabel("Я согласен(на) на обработку персональных данных в рамках тестирования").check();
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.locator(".progress-track")).toBeVisible();
}

/** Вход + согласие одним шагом — для тестов, которым интересен только сам процесс тестирования. */
export async function startTesting(page: Page, entryCode: string = DEMO_ENTRY_CODE) {
  await enterViaCorporateLink(page, entryCode);
  await acceptConsent(page);
}

export async function answerCurrentQuestion(page: Page) {
  const previousQuestion = await page.locator(".card h2").innerText();
  await page.locator(".option-card").first().click();
  await expect(page.locator(".card h2")).not.toHaveText(previousQuestion);
}

export async function completeStage(page: Page, questionCount: number = DUMMY_QUESTIONNAIRE_LENGTH) {
  for (let i = 0; i < questionCount; i += 1) {
    await answerCurrentQuestion(page);
  }
}
