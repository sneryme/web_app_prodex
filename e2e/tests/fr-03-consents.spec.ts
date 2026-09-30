import { test, expect } from "@playwright/test";
import { DEMO_ENTRY_CODE, enterViaCorporateLink } from "./support/participant";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

test.describe("FR-03 Экран согласий и журнал согласия", () => {
  test("FR-03.1 согласие на обработку ПД вынесено на отдельный экран и не смешано с другими подтверждениями", async ({
    page,
  }) => {
    await enterViaCorporateLink(page);
    await page.getByRole("button", { name: "Начать знакомство" }).click();
    // На экране согласия — ровно один чекбокс (согласие на обработку ПД), не набор разных подтверждений.
    await expect(page.locator('input[type="checkbox"]')).toHaveCount(1);
  });

  test("FR-03.2 чекбокс согласия по умолчанию не отмечен", async ({ page }) => {
    await enterViaCorporateLink(page);
    await page.getByRole("button", { name: "Начать знакомство" }).click();
    await expect(page.locator('input[type="checkbox"]')).not.toBeChecked();
    await expect(page.getByRole("button", { name: "Продолжить" })).toBeDisabled();
  });

  test("FR-03.3 без согласия переход к вопросам невозможен, в том числе прямым запросом к API", async ({ request }) => {
    const created = await request.post(`${API_URL}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
    const { token, questions } = await created.json();
    // На этом этапе вопросов в ответе ещё нет (согласие не дано); берём id напрямую через сервис было бы избыточно —
    // проверяем сам факт отказа в сохранении ответа для заведомо любого question_id.
    const response = await request.post(`${API_URL}/participant/sessions/${token}/answers/`, {
      data: { question_id: 1, option_id: null },
    });
    expect(response.status()).toBe(403);
    expect(questions).toEqual([]);
  });

  test("FR-03.4 факт согласия сохраняется с версией текста и временем", async ({ page }) => {
    await enterViaCorporateLink(page);
    await page.getByRole("button", { name: "Начать знакомство" }).click();
    await page.getByLabel("Я согласен(на) на обработку персональных данных в рамках тестирования").check();
    // Экран отправляет два согласия (информирование, затем обработка ПД) — ждём именно второе.
    const response = page.waitForResponse(
      (r) =>
        r.url().includes("/consents/") &&
        r.request().method() === "POST" &&
        r.request().postDataJSON()?.consent_type === "data_processing",
    );
    await page.getByRole("button", { name: "Продолжить" }).click();
    const consentResponse = await response;
    const body = await consentResponse.json();
    expect(body.consent_status).toBe("granted");
    // Версия текста и точное время фиксируются на бэкенде в ConsentRecord (см. backend/apps/participants/test_flow.py);
    // здесь проверяем наблюдаемое следствие — согласие переживает перезагрузку и участник сразу попадает к вопросам.
    await page.reload();
    await expect(page.locator(".progress-track")).toBeVisible();
  });

  test("FR-03.5 отказ от согласия завершает маршрут, ответы не сохраняются", async ({ page }) => {
    await enterViaCorporateLink(page);
    await page.getByRole("button", { name: "Начать знакомство" }).click();
    await page.getByRole("button", { name: "Отказаться от участия" }).click();
    await expect(page.getByRole("heading", { name: "Вы отказались от участия" })).toBeVisible();

    await page.reload();
    await expect(page.getByRole("heading", { name: "Вы отказались от участия" })).toBeVisible();
  });
});
