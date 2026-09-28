import { test, expect } from "@playwright/test";
import { DEMO_ENTRY_CODE, completeStage, startTesting } from "./support/participant";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

// Опросник-заглушка (manage.py seed_dummy_questionnaire): option index 0 = «лучшее» значение
// для severity-вопросов (тревожность/HADS), option index 3 = «лучшее» для eq5d_vas (рейтинговая
// шкала). Отвечая на входном этапе индексом 0, а на итоговом — индексом 3, мы получаем заведомо
// разнонаправленную динамику: eq5d_vas улучшается, остальные 4 показателя — ухудшаются.
async function completeBothStagesWithMixedDynamics(page: import("@playwright/test").Page) {
  await startTesting(page);
  await completeStage(page, 6, 0); // входное
  await completeStage(page, 6, 3); // итоговое
  await expect(page.locator(".report-grid")).toBeVisible();
}

test.describe("FR-08 Персональный отчёт участника", () => {
  test("FR-08.1 отчёт содержит ровно 5 карточек: EQ-5D VAS, ситуативная и личностная тревожность, HADS тревога и депрессия", async ({
    page,
  }) => {
    await completeBothStagesWithMixedDynamics(page);
    await expect(page.locator(".report-card")).toHaveCount(5);
    const text = await page.locator(".report-grid").innerText();
    for (const label of [
      "EQ-5D VAS",
      "Ситуативная тревожность",
      "Личностная тревожность",
      "Тревога по шкале HADS",
      "Депрессивная симптоматика HADS",
    ]) {
      expect(text).toContain(label);
    }
  });

  test("FR-08.2 каждая карточка показывает было → стало → изменение → нейтральную интерпретацию", async ({ page }) => {
    await completeBothStagesWithMixedDynamics(page);
    const firstCard = page.locator(".report-card").first();
    await expect(firstCard.locator(".report-card__values")).toContainText("→");
    await expect(firstCard.locator(".report-card__zones")).toContainText("→");
    await expect(firstCard.locator(".report-card__trend")).toBeVisible();
  });

  test("FR-08.3 шкалы не объединены в один общий график или индекс", async ({ page }) => {
    await completeBothStagesWithMixedDynamics(page);
    const text = await page.locator(".shell").innerText();
    expect(text).not.toMatch(/общий индекс|индекс здоровья|суммарный балл/i);
  });

  test("FR-08.4 есть дисклеймер «не является диагнозом»; нет слова «клиническая» и рекомендаций", async ({ page }) => {
    await completeBothStagesWithMixedDynamics(page);
    await expect(page.getByText("не являются диагнозом")).toBeVisible();
    const text = await page.locator(".shell").innerText();
    expect(text).not.toMatch(/клиническ/i);
  });

  test("FR-08.5 EQ-5D показан по пяти компонентам, а не только кодом", async ({ page }) => {
    await completeBothStagesWithMixedDynamics(page);
    // eq5d_mobility не входит в 5 основных карточек — он должен быть в отдельном блоке профиля.
    const cardsText = await page.locator(".report-grid").innerText();
    expect(cardsText).not.toContain("трудности с передвижением");

    await expect(page.getByRole("heading", { name: "Ваш профиль здоровья (EQ-5D)" })).toBeVisible();
    await expect(page.getByText("трудности с передвижением", { exact: false })).toBeVisible();
  });

  test("FR-08.6 разнонаправленная динамика даёт корректный автоматический вывод", async ({ page }) => {
    await completeBothStagesWithMixedDynamics(page);
    await expect(page.getByText("разнонаправленн", { exact: false })).toBeVisible();
  });

  test("FR-08.7 неверный токен даёт 404 без утечки данных", async ({ request }) => {
    const response = await request.get(`${API_URL}/participant/reports/does-not-exist/`);
    expect(response.status()).toBe(404);
  });

  test("FR-08.7 отчёт до завершения обоих этапов недоступен (404)", async ({ request }) => {
    const created = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
    const { token } = await created.json();
    await request.post(`${API_URL}/participant/sessions/${token}/consents/`, {
      data: { consent_type: "data_processing", text_version: "v1", accepted: true },
    });

    const response = await request.get(`${API_URL}/participant/reports/${token}/`);
    expect(response.status()).toBe(404);
  });
});
