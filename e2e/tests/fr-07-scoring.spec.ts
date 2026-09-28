import { test, expect } from "@playwright/test";
import { DEMO_ENTRY_CODE } from "./support/participant";
import { scenario } from "./support/scenario";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

async function startSession(request: import("@playwright/test").APIRequestContext) {
  const created = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
  const { token } = await created.json();
  await request.post(`${API_URL}/participant/sessions/${token}/consents/`, {
    data: { consent_type: "data_processing", text_version: "v1", accepted: true },
  });
  return token as string;
}

async function answerAll(
  request: import("@playwright/test").APIRequestContext,
  token: string,
  optionIndex: number,
) {
  let state = await (await request.get(`${API_URL}/participant/sessions/${token}/`)).json();
  for (const question of state.questions) {
    const option = question.options[optionIndex];
    const response = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
      data: { question_id: question.id, option_id: option.id },
    });
    state = await response.json();
  }
  return state;
}

test.describe("FR-07 Автоматический scoring и связка «до / после»", () => {
  // Формулы и границы зон — черновые, до утверждения методологом (project/PROJECT_RULES.md №5);
  // эталонных баллов и границ зон интерпретации от методолога пока нет.
  scenario("FR-07.1", "эталонный набор ответов даёт ожидаемые баллы по 5 показателям");
  scenario("FR-07.2", "граничные баллы попадают в правильные зоны интерпретации");

  test("FR-07.3 итоговые результаты связываются со входными по токену", async ({ request }) => {
    const token = await startSession(request);
    await answerAll(request, token, 0); // входное — везде первый вариант
    await answerAll(request, token, 3); // итоговое — везде последний вариант

    const report = await (await request.get(`${API_URL}/participant/reports/${token}/`)).json();
    // «Связка по токену» наблюдаема как различие before/after — оба взяты из одной и той же сессии.
    for (const card of report.cards) {
      expect(card.before.raw_score).not.toBe(card.after.raw_score);
      expect(card.change).not.toBe(0);
    }
  });

  test("FR-07.4 без входного этапа «до / после» не строится", async ({ request }) => {
    const token = await startSession(request);
    // Входное тестирование не завершено — отвечаем только на первый вопрос.
    const state = await (await request.get(`${API_URL}/participant/sessions/${token}/`)).json();
    await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
      data: { question_id: state.questions[0].id, option_id: state.questions[0].options[0].id },
    });

    const response = await request.get(`${API_URL}/participant/reports/${token}/`);
    expect(response.status()).toBe(404);
  });

  test("FR-07.5 три методики не объединяются в общий индекс", async ({ request }) => {
    const token = await startSession(request);
    await answerAll(request, token, 1);
    await answerAll(request, token, 2);

    const report = await (await request.get(`${API_URL}/participant/reports/${token}/`)).json();
    const forbiddenKeys = ["index", "overall_score", "total_score", "combined_score"];
    for (const key of forbiddenKeys) {
      expect(Object.keys(report)).not.toContain(key);
    }
  });
});
