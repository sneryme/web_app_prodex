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

/**
 * Реальный Спилбергер–Ханин намеренно сбалансирован: 10 из 20 пунктов в каждом блоке —
 * прямые, 10 — реверсивные (так контролируют response bias). Поэтому "всегда вариант с
 * индексом 0 / всегда с индексом 3" — как было с единообразной опросником-заглушкой — даёт
 * на реальных данных нулевую суммарную разницу (прямые и реверсивные пункты гасят друг друга).
 * Выбираем по `value` (минимальный/максимальный балл конкретного вопроса), а не по индексу
 * карточки — тогда направление консистентно независимо от реверсивности пункта.
 */
async function answerAll(request: import("@playwright/test").APIRequestContext, token: string, pick: "min" | "max") {
  let state = await (await request.get(`${API_URL}/participant/sessions/${token}/`)).json();
  for (const question of state.questions) {
    // EQ-5D VAS не имеет вариантов ответа — это свободный числовой ввод 0–100, не карточка.
    let data;
    if (question.options.length > 0) {
      const values = question.options.map((o: { value: number }) => o.value);
      const target = pick === "min" ? Math.min(...values) : Math.max(...values);
      const option = question.options[values.indexOf(target)];
      data = { question_id: question.id, option_id: option.id };
    } else {
      data = { question_id: question.id, raw_value: pick === "min" ? "0" : "100" };
    }
    const response = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, { data });
    state = await response.json();
  }
  return state;
}

test.describe("FR-07 Автоматический scoring и связка «до / после»", () => {
  // Границы зон HADS и Спилбергера–Ханина теперь реальные (см. apps/assessments/scoring.py,
  // project/CHANGELOG.md) и проверены на backend (apps/assessments/test_scoring.py). Этих двух
  // e2e-сценариев (эталонный набор ответов целиком через UI/API, границы зон через конкретные
  // суммы по подшкале) пока нет — автоматизировать их через UI сложнее, чем через unit-тесты.
  scenario("FR-07.1", "эталонный набор ответов даёт ожидаемые баллы по 5 показателям");
  scenario("FR-07.2", "граничные баллы попадают в правильные зоны интерпретации");

  test("FR-07.3 итоговые результаты связываются со входными по токену", async ({ request }) => {
    const token = await startSession(request);
    await answerAll(request, token, "min"); // входное
    await answerAll(request, token, "max"); // итоговое

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
    await answerAll(request, token, "min");
    await answerAll(request, token, "max");

    const report = await (await request.get(`${API_URL}/participant/reports/${token}/`)).json();
    const forbiddenKeys = ["index", "overall_score", "total_score", "combined_score"];
    for (const key of forbiddenKeys) {
      expect(Object.keys(report)).not.toContain(key);
    }
  });
});
