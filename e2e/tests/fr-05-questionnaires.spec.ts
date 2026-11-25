import { expect, test } from "@playwright/test";
import { DEMO_ENTRY_CODE, startTesting } from "./support/participant";
import { scenario } from "./support/scenario";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

test.describe("FR-05 Три методики: EQ-5D, Спилбергер–Ханин, HADS", () => {
  // FR-05.1 требует, чтобы разделы (на каком вы сейчас этапе — EQ-5D/HADS/СШХ) были подписаны в
  // интерфейсе; сейчас экран вопроса показывает только общий счётчик "Вопрос N из 60", без
  // привязки к конкретной методике — это отдельная фронтенд-доработка, не сделанная в рамках
  // загрузки реальных методик (`manage.py seed_real_questionnaires`).
  scenario("FR-05.1", "маршрут содержит все три методики, разделы подписаны");

  test("FR-05.2 число вопросов каждой методики равно утверждённой версии (5 EQ-5D + 1 VAS + 14 HADS + 40 СШХ)", async ({
    request,
  }) => {
    const created = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
    const { token } = await created.json();
    const consent = await request.post(`${API_URL}/participant/sessions/${token}/consents/`, {
      data: { consent_type: "data_processing", text_version: "v1", accepted: true },
    });
    expect(consent.status()).toBe(201);
    const state = await consent.json();

    const counts: Record<string, number> = {};
    for (const q of state.questions) counts[q.indicator_code] = (counts[q.indicator_code] ?? 0) + 1;

    expect(state.questions.length).toBe(60);
    for (const code of ["eq5d_mobility", "eq5d_self_care", "eq5d_daily_activities", "eq5d_pain", "eq5d_anxiety_depression", "eq5d_vas"]) {
      expect(counts[code]).toBe(1);
    }
    expect(counts["hads_anxiety"]).toBe(7);
    expect(counts["hads_depression"]).toBe(7);
    expect(counts["situational_anxiety"]).toBe(20);
    expect(counts["trait_anxiety"]).toBe(20);
  });

  // FR-05.3 — версия методики фиксируется вместе с ответом структурно (AnswerResponse.question
  // → Question.questionnaire_version, PROTECT — нельзя потерять связь задним числом), но текущий
  // API-ответ сессии не отдаёт questionnaire_version по каждому вопросу, поэтому через e2e это
  // не проверить без расширения контракта; факт фиксации версии стоит проверять backend-тестом.
  scenario("FR-05.3", "версия методики фиксируется вместе с ответами");

  test("FR-05.4 вопрос нельзя пропустить: без ответа кнопка «Далее» недоступна", async ({ page }) => {
    await startTesting(page);
    await expect(page.getByRole("button", { name: "Далее" })).toBeDisabled();
  });
});
