import { test, expect } from "@playwright/test";
import { DEMO_ENTRY_CODE, completeStage, startTesting } from "./support/participant";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

test.describe("FR-04 Автоматическое определение этапа", () => {
  test("FR-04.1 новый токен попадает на входное тестирование", async ({ page }) => {
    await startTesting(page);
    await expect(page.getByText("Входное тестирование", { exact: false })).toBeVisible();
  });

  test("FR-04.2 токен с завершённым входным попадает на итоговое тестирование", async ({ page }) => {
    await startTesting(page);
    await completeStage(page);
    await expect(page.getByText("Итоговое тестирование", { exact: false })).toBeVisible();
  });

  test("FR-04.3 ручного выбора «первичный/вторичный» в интерфейсе нет", async ({ page }) => {
    await startTesting(page);
    const text = await page.locator(".shell").innerText();
    expect(text).not.toMatch(/первичн|вторичн/i);
    // Единственный контрол выбора на экране вопроса — варианты ответа, а не переключатель этапов.
    await expect(page.locator("select, [role='radiogroup']")).toHaveCount(0);
  });

  test("FR-04.4 токен с завершёнными этапами открывает отчёт, а не повторное тестирование", async ({ page }) => {
    await startTesting(page);
    await completeStage(page); // входное
    await completeStage(page); // итоговое
    await expect(page.getByRole("heading", { name: "Вы прошли оба этапа тестирования" })).toBeVisible();
    await expect(page.locator(".option-card")).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("heading", { name: "Вы прошли оба этапа тестирования" })).toBeVisible();
  });

  test("FR-04.5 итоговое нельзя начать до завершения входного (прямые вызовы API)", async ({ request }) => {
    const created = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
    const { token } = await created.json();
    await request.post(`${API_URL}/participant/sessions/${token}/consents/`, {
      data: { consent_type: "data_processing", text_version: "v1", accepted: true },
    });
    const initialState = await (await request.get(`${API_URL}/participant/sessions/${token}/`)).json();
    const questions = initialState.questions;
    expect(questions.length).toBeGreaterThan(1);

    // Отвечаем на все вопросы, кроме последнего, — этап должен оставаться входным всё это время.
    for (let i = 0; i < questions.length - 1; i += 1) {
      const response = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
        data: { question_id: questions[i].id, option_id: questions[i].options[0].id },
      });
      const body = await response.json();
      expect(body.stage).toBe("baseline");
    }

    // И только после последнего ответа сервер сам переводит участника в итоговое тестирование.
    const last = questions[questions.length - 1];
    const finalResponse = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
      data: { question_id: last.id, option_id: last.options[0].id },
    });
    const finalBody = await finalResponse.json();
    expect(finalBody.stage).toBe("followup");
  });
});
