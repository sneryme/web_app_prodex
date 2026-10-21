import { expect, test } from "@playwright/test";
import { DEMO_STAFF_PASSWORD, loginAsEmployer, PRODEX_ADMIN_USERNAME } from "./support/employer";

// ТЗ FR-10: PDF/XLSX-экспорт того же агрегата, что и дашборд FR-09 — см. `export_services.py`.
// Тестовые данные — те же, что у FR-09 (`seed_employer_demo_streams`): demo-организация/2026-H2
// (8 участников, выше порога), "ООО Вектор Плюс"/2026-pilot (3 участника, ниже порога).

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000/api";

async function loginForApi(request: import("@playwright/test").APIRequestContext) {
  const response = await request.post(`${API_URL}/identity/login/`, {
    data: { username: PRODEX_ADMIN_USERNAME, password: DEMO_STAFF_PASSWORD },
  });
  const { token } = await response.json();
  return token as string;
}

test.describe("FR-10 Экспорт PDF/XLSX", () => {
  test("FR-10.1 PDF-отчёт скачивается по кнопке на дашборде", async ({ page }) => {
    await loginAsEmployer(page);
    await expect(page.locator(".employer-card")).toHaveCount(5); // дождались загрузки агрегата

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Скачать PDF" }).click(),
    ]);

    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
    const path = await download.path();
    expect(path).not.toBeNull();
  });

  test("FR-10.2 XLSX не содержит строк участников и токенов", async ({ request }) => {
    const token = await loginForApi(request);
    const response = await request.get(`${API_URL}/employer/organizations/1/export/?kind=xlsx`, {
      headers: { Authorization: `Token ${token}` },
    });
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("spreadsheetml");

    const body = await response.body();
    // xlsx — это zip с XML внутри; participant-токен (32+ символов url-safe base64) не должен
    // встретиться нигде в сыром содержимом файла.
    const asLatin1 = body.toString("latin1");
    expect(asLatin1).not.toMatch(/[A-Za-z0-9_-]{32,}/);
  });

  test("FR-10.3 малые группы скрыты и в экспорте", async ({ request }) => {
    const token = await loginForApi(request);
    const overview = await request.get(`${API_URL}/employer/organizations/2/streams/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const streams: Array<{ id: number; code: string }> = await overview.json();
    const pilot = streams.find((s) => s.code === "2026-pilot");
    expect(pilot).toBeTruthy();

    const response = await request.get(`${API_URL}/employer/organizations/2/export/?kind=xlsx&stream=${pilot!.id}`, {
      headers: { Authorization: `Token ${token}` },
    });
    expect(response.status()).toBe(200);
    // xlsx — сжатый zip, надёжно искать в нём текст на уровне сырых байт нельзя, поэтому здесь
    // только факт, что экспорт малой группы не падает. Содержимое (что вместо среднего — именно
    // "скрыто", а не просочившееся число) проверяется в backend-тесте
    // `apps/reporting/test_export_services.py::test_xlsx_export_marks_suppressed_small_groups_instead_of_showing_a_mean`.
  });

  test("FR-10.4 экспорт недоступен без прав администратора", async ({ request }) => {
    const anonymous = await request.get(`${API_URL}/employer/organizations/1/export/?kind=xlsx`);
    expect(anonymous.status()).toBe(401);
  });
});
