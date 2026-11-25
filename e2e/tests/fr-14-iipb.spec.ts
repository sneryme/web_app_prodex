import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { DEMO_ENTRY_CODE } from "./support/participant";

const API = process.env.E2E_API_URL ?? "http://localhost:8000/api";
const report = JSON.parse(readFileSync(path.join(__dirname, "fixtures/iipb-report.json"), "utf8"));
const targets: Record<string, number> = {
  hads_anxiety: 9, hads_depression: 6, situational_anxiety: 46, trait_anxiety: 48,
  eq5d_mobility: 1, eq5d_self_care: 1, eq5d_daily_activities: 2,
  eq5d_pain: 2, eq5d_anxiety_depression: 3, eq5d_vas: 60,
};

test.beforeEach(async ({ page }) => {
  // Внешние шрифты не должны определять доступность локального сценария в тестах.
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\//, route => route.abort());
});

async function create(request: any) {
  const response = await request.post(`${API}/participant/sessions/`, { data: { entry_code: DEMO_ENTRY_CODE } });
  expect(response.status()).toBe(201);
  const home = await response.json();
  const bundle = home.bundles.find((item: any) => item.code === "iipb-0.1");
  expect(bundle, "Запустите seed_iipb_methodology").toBeTruthy();
  return { home, bundle };
}

test("ИИПБ: входной результат появляется сразу, повторный замер закрыт на 7 дней", async ({ page, request }, info) => {
  test.setTimeout(90_000);
  const { home, bundle } = await create(request);
  for (const consent_type of ["informed_notice", "data_processing"]) {
    const response = await request.post(`${API}/participant/sessions/${home.token}/consents/`, {
      data: { consent_type, text_version: "iipb-0.1", accepted: true, bundle_id: bundle.id },
    });
    expect(response.status()).toBe(201);
  }
  const selected = await request.post(`${API}/participant/sessions/${home.token}/bundles/`, { data: { bundle_id: bundle.id } });
  const state = await selected.json();
  const remaining = { ...targets };
  const counts: Record<string, number> = {};
  for (const question of state.questions) counts[question.indicator_code] = (counts[question.indicator_code] ?? 0) + 1;
  for (const question of state.questions.slice(0, -1)) {
    const code = question.indicator_code;
    const minimum = Math.min(...question.options.map((option: any) => option.value));
    const maximum = Math.max(...question.options.map((option: any) => option.value));
    const value = Math.min(maximum, remaining[code] - (counts[code] - 1) * minimum);
    const option = question.options.find((option: any) => option.value === value);
    const response = await request.post(`${API}/participant/sessions/${home.token}/answers/`, {
      data: { bundle_id: bundle.id, stage: "baseline", question_id: question.id, option_id: option.id },
    });
    expect(response.status()).toBe(200);
    remaining[code] -= value;
    counts[code] -= 1;
  }
  await page.goto(`/?token=${home.token}`);
  await page.locator('[data-bundle-code="iipb-0.1"]').click();
  const slider = page.locator('input[type="range"]');
  await expect(slider).toBeVisible();
  await slider.evaluate((element: HTMLInputElement) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(element, "60");
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.getByRole("button", { name: "Сохранить ответ" }).click();
  await expect(page.getByRole("heading", { name: "Ваш входной результат" })).toBeVisible();
  await expect(page.locator(".iipb-value")).toHaveText("66%");
  await expect(page.getByRole("button", { name: "Ожидаем итоговый замер" })).toBeDisabled();
  await expect(page.getByText("Y1 · Высокая ситуативная тревожность", { exact: true })).toBeVisible();
  await page.reload();
  await page.locator('[data-bundle-code="iipb-0.1"]').click();
  await expect(page.locator(".iipb-value")).toHaveText("66%");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("baseline.png"), fullPage: true });
});

test("ИИПБ: отдельные подтверждения и последовательность опросников", async ({ page, request }) => {
  const { home } = await create(request);
  await page.goto(`/?token=${home.token}`);
  await page.locator('[data-bundle-code="iipb-0.1"]').click();
  await page.getByRole("button", { name: "Начать знакомство" }).click();
  const proceed = page.getByRole("button", { name: "Продолжить", exact: true });
  await page.getByLabel(/Я согласен\(на\) на обработку сведений/).check();
  await expect(proceed).toBeDisabled();
  await page.getByLabel(/Мне исполнилось 18 лет/).check();
  await page.getByLabel(/Я ознакомлен\(а\)/).check();
  await proceed.click();
  await expect(page.locator('[data-questionnaire-code="hads"]')).toBeEnabled();
  await expect(page.locator('[data-questionnaire-code="stai"]')).toBeDisabled();
  await expect(page.locator('[data-questionnaire-code="eq5d"]')).toBeDisabled();
});

test("ИИПБ: красный флаг остаётся заметным при положительной динамике индекса", async ({ page }, info) => {
  const home = { token: "preview-iipb", organization_id: 1, consent_status: "granted", bundles: [
    { id: 1, code: "iipb-0.1", name: "ИИПБ v0.1", status: "completed", baseline: { answered: 60, total: 60 }, followup: { answered: 60, total: 60 }, questionnaires: [] },
  ] };
  await page.route("**/api/participant/**", async route => {
    const url = new URL(route.request().url());
    const body = url.pathname.includes("/reports/") ? report : url.pathname.endsWith("/bundles/")
      ? { token: "preview-iipb", bundle_id: 1, consent_status: "granted", stage: null, questions: [], questionnaires: [], progress: { answered: 0, total: 0 } }
      : home;
    await route.fulfill({ json: body });
  });
  await page.goto("/?token=preview-iipb");
  await page.locator('[data-bundle-code="iipb-0.1"]').click();
  await expect(page.locator(".iipb-alert--red").getByText("Требуется консультация специалиста")).toBeVisible();
  await expect(page.locator(".iipb-value").last()).toHaveText("77%");
  await expect(page.locator(".iipb-delta")).toHaveText("+11 п.п.");
  await expect(page.getByText(/Фоновый маркер; в индекс и динамику не входит/)).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("report.png"), fullPage: true });
});

test("ИИПБ: работодатель видит среднее, медиану и парную динамику", async ({ page, isMobile }, info) => {
  test.skip(isMobile, "Дашборд работодателя предназначен для компьютера");
  await page.addInitScript(() => {
    localStorage.setItem("pez_employer_token", "preview-staff");
    localStorage.setItem("pez_employer_staff", JSON.stringify({ role_display: "Администратор организации", organization: { id: 1, name: "Демо ИИПБ" } }));
  });
  const stage = { participant_count: 8, is_suppressed: false, mean: 66, median: 66, red_flag_count: 0, yellow_flag_count: 8, zone_distribution: { "Лёгкое снижение": 8 }, flag_distribution: { Y1: 8 }, trait_distribution: { "высокая": 8 } };
  await page.route("**/api/employer/**", async route => {
    const pathname = new URL(route.request().url()).pathname;
    const body = pathname.endsWith("/overview/") ? {
      organization: { id: 1, name: "Демо ИИПБ" }, stream: null, coverage: { participants: 8 },
      completion: { baseline_completed: 8, followup_completed: 8 }, indicators: [],
      iipb: { version: "0.1", version_date: "2026-11-16", threshold: 5,
        notice: report.iipb.baseline.notice, dynamics_notice: report.iipb.dynamics.notice,
        baseline: stage, followup: { ...stage, mean: 79, median: 79, yellow_flag_count: 0, zone_distribution: { "Сохранное благополучие": 8 } },
        trend: { paired_count: 8, is_suppressed: false, mean_delta: 13, median_delta: 13, improved: 8, worsened: 0, stable: 0 },
      },
    } : pathname.endsWith("/bundles/") ? [{ id: 1, code: "iipb-0.1", name: "ИИПБ v0.1" }]
      : pathname.endsWith("/streams/") ? [] : [{ id: 1, name: "Демо ИИПБ" }];
    await route.fulfill({ json: body });
  });
  await page.goto("/employer");
  await expect(page.getByRole("heading", { name: /Психоэмоциональное благополучие · ИИПБ/ })).toBeVisible();
  await expect(page.getByText("Средняя Δ: 13 п.п. · медианная Δ: 13 п.п.")).toBeVisible();
  await page.screenshot({ path: info.outputPath("employer.png"), fullPage: true });
});
