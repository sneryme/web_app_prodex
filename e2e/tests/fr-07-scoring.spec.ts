import { test, expect } from "@playwright/test";
import { DEMO_ENTRY_CODE } from "./support/participant";
import { scenario } from "./support/scenario";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

async function startSession(request: import("@playwright/test").APIRequestContext) {
  const created = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
  const { token, bundles } = await created.json();
  const bundle = bundles.find((item: {code: string}) => item.code === "prodex-v1");
  expect(bundle).toBeTruthy();
  await request.post(`${API_URL}/participant/sessions/${token}/consents/`, {
    data: { bundle_id: bundle.id, consent_type: "data_processing", text_version: "v1", accepted: true },
  });
  return { token: token as string, bundleId: bundle.id as number };
}

/**
 * Реальный Спилбергер–Ханин намеренно сбалансирован: 10 из 20 пунктов в каждом блоке —
 * прямые, 10 — реверсивные (так контролируют response bias). Поэтому "всегда вариант с
 * индексом 0 / всегда с индексом 3" — как было с единообразной опросником-заглушкой — даёт
 * на реальных данных нулевую суммарную разницу (прямые и реверсивные пункты гасят друг друга).
 * Выбираем по `value` (минимальный/максимальный балл конкретного вопроса), а не по индексу
 * карточки — тогда направление консистентно независимо от реверсивности пункта.
 */
async function answerAll(request: import("@playwright/test").APIRequestContext, token: string, bundleId: number, pick: "min" | "max") {
  const selected = await request.post(`${API_URL}/participant/sessions/${token}/bundles/`, { data: { bundle_id: bundleId } });
  expect(selected.ok()).toBeTruthy();
  const state = await selected.json();
  for (const question of state.questions) {
    // EQ-5D VAS не имеет вариантов ответа — это свободный числовой ввод 0–100, не карточка.
    let data;
    if (question.options.length > 0) {
      const values = question.options.map((o: { value: number }) => o.value);
      const target = pick === "min" ? Math.min(...values) : Math.max(...values);
      const option = question.options[values.indexOf(target)];
      data = { stage: state.stage, question_id: question.id, option_id: option.id };
    } else {
      data = { stage: state.stage, question_id: question.id, raw_value: pick === "min" ? "0" : "100" };
    }
    const response = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
      data: { ...data, bundle_id: bundleId },
    });
    expect(response.status()).toBe(200);
  }
}

test.describe("FR-07 Автоматический scoring и связка «до / после»", () => {
  // Границы зон HADS и Спилбергера–Ханина теперь реальные (см. apps/assessments/scoring.py,
  // project/CHANGELOG.md) и проверены на backend (apps/assessments/test_scoring.py). Этих двух
  // e2e-сценариев (эталонный набор ответов целиком через UI/API, границы зон через конкретные
  // суммы по подшкале) пока нет — автоматизировать их через UI сложнее, чем через unit-тесты.
  scenario("FR-07.1", "эталонный набор ответов даёт ожидаемые баллы по 5 показателям");
  scenario("FR-07.2", "граничные баллы попадают в правильные зоны интерпретации");

  test("FR-07.3 итоговые результаты связываются со входными по токену", async ({ request }) => {
    const { token, bundleId } = await startSession(request);
    await answerAll(request, token, bundleId, "min");
    await answerAll(request, token, bundleId, "max");

    const response = await request.get(`${API_URL}/participant/reports/${token}/?bundle_id=${bundleId}`);
    expect(response.status()).toBe(200);
    const report = await response.json();
    expect(report.cards).toHaveLength(5);
    // «Связка по токену» наблюдаема как различие before/after — оба взяты из одной и той же сессии.
    for (const card of report.cards) {
      expect(card.before.raw_score).not.toBe(card.after.raw_score);
      expect(card.change).not.toBe(0);
    }
  });

  test("FR-07.4 без входного этапа «до / после» не строится", async ({ request }) => {
    const { token, bundleId } = await startSession(request);
    // Входное тестирование не завершено — отвечаем только на первый вопрос.
    const selected = await request.post(`${API_URL}/participant/sessions/${token}/bundles/`, { data: { bundle_id: bundleId } });
    const state = await selected.json();
    await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
      data: { bundle_id: bundleId, stage: state.stage, question_id: state.questions[0].id, option_id: state.questions[0].options[0].id },
    });

    const response = await request.get(`${API_URL}/participant/reports/${token}/?bundle_id=${bundleId}`);
    expect(response.status()).toBe(404);
  });

  test("FR-07.5 три методики не объединяются в общий индекс", async ({ request }) => {
    const { token, bundleId } = await startSession(request);
    await answerAll(request, token, bundleId, "min");
    await answerAll(request, token, bundleId, "max");

    const response = await request.get(`${API_URL}/participant/reports/${token}/?bundle_id=${bundleId}`);
    expect(response.status()).toBe(200);
    const report = await response.json();
    const forbiddenKeys = ["index", "overall_score", "total_score", "combined_score"];
    for (const key of forbiddenKeys) {
      expect(Object.keys(report)).not.toContain(key);
    }
  });
});
