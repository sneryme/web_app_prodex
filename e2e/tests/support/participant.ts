import { expect, type Page } from "@playwright/test";

// Демо-организация создаётся командой `manage.py seed_demo_organization` (см. README).
const legacy = process.env.E2E_SUITE === "legacy";
export const DEMO_ENTRY_CODE = process.env.E2E_ENTRY_CODE ?? (legacy ? "demo-entry-code" : "iipb-presentation");
const DEFAULT_BUNDLE = legacy ? "prodex-v1" : "iipb-0.1";

// Создание сессии/сохранение согласия — асинхронные запросы к API; каждый хелпер дожидается
// видимого следствия запроса, чтобы тесты не ловили гонку с недорисованным экраном.

export async function openTokenNotice(page: Page, entryCode = DEMO_ENTRY_CODE) {
  await page.goto(`/?code=${entryCode}`);
  const entryForm = page.locator(".stream-entry-form");
  await expect(entryForm).toBeVisible();
  const streamSelect = entryForm.getByLabel("Отдел", { exact: true });
  if (await streamSelect.count()) {
    if (legacy) {
      const demoStream = streamSelect.getByRole("option", { name: /^demo-stream(?: \(demo-stream\))?$/ });
      const value = await demoStream.getAttribute("value");
      if (!value) throw new Error("Legacy demo stream is unavailable.");
      await streamSelect.selectOption(value);
    } else {
      await streamSelect.selectOption({ index: 1 });
    }
  }
  await entryForm.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.locator(".token-box code")).toBeVisible();
}

export async function readParticipantToken(page: Page) {
  const cookies = await page.context().cookies(page.url());
  return cookies.find((cookie) => cookie.name === "pez_participant_token")?.value ?? null;
}

export async function enterViaCorporateLink(page: Page, entryCode = DEMO_ENTRY_CODE, bundleCode = DEFAULT_BUNDLE) {
  await openTokenNotice(page, entryCode);
  await page.getByLabel("Я сохранил(а) код участника").check();
  await page.getByRole("button", { name: "Продолжить" }).click();
  await resumeBundle(page, bundleCode);
  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();
}

/**
 * Тест не начинается сразу после согласия/после завершения этапа — показывается стартовый экран
 * этапа (StageIntroScreen.tsx) с кнопкой «Начать…». Если его нет (уже отвеченный вопрос, отчёт) —
 * не блокируем тест ожиданием: кнопка просто не появится.
 */
export async function dismissStageIntro(page: Page) {
  const startButton = page.getByRole("button", { name: /^Начать (тестирование|итоговое тестирование)$/ });
  try {
    await startButton.waitFor({ state: "visible", timeout: 1000 });
  } catch {
    return;
  }
  await startButton.click();
}

export async function acceptConsent(page: Page) {
  await page.getByRole("button", { name: "Начать знакомство" }).click();
  await page.getByLabel("Я согласен(на) на обработку персональных данных в рамках тестирования").check();
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.locator(".test-menu")).toBeVisible();
  const firstTest = page.locator('.test-menu__item[data-completed="false"]').first();
  if (await firstTest.count()) await firstTest.click();
  await dismissStageIntro(page);
  await expect(page.locator(".progress-track")).toBeVisible();
}

/** Вход + согласие одним шагом — для тестов, которым интересен только сам процесс тестирования. */
export async function startTesting(page: Page, entryCode: string = DEMO_ENTRY_CODE, bundleCode?: string) {
  await enterViaCorporateLink(page, entryCode, bundleCode);
  await acceptConsent(page);
}

export async function resumeBundle(page: Page, bundleCode = DEFAULT_BUNDLE) {
  const bundle = page.locator(`.bundle-menu__item[data-bundle-code="${bundleCode}"]`);
  await expect(bundle).toBeVisible();
  await bundle.click();
}

async function readTotalQuestions(page: Page): Promise<number> {
  const countAttribute = await page.locator("[data-question-count]").getAttribute("data-question-count");
  if (countAttribute !== null) return Number(countAttribute);
  // .tag — text-transform:uppercase в CSS, поэтому innerText() отдаёт видимый текст КАПСОМ
  // ("...ИЗ 60"), а не как он записан в JSX ("...из 60") — регэксп должен это учитывать.
  const tagText = await page.locator(".tag").first().innerText();
  const match = tagText.match(/из (\d+)/i);
  if (!match) throw new Error(`Не удалось определить количество вопросов из текста тега: "${tagText}"`);
  return Number(match[1]);
}

/**
 * Отвечает на текущий вопрос. Реальный набор методик (EQ-5D/HADS/Спилбергер–Ханин,
 * `manage.py seed_real_questionnaires`) — это не единообразные 4-вариантные карточки:
 * у измерений EQ-5D по 3 варианта, а у VAS вариантов нет вовсе (свободный числовой ввод,
 * см. `.vas-input` в QuestionFlow.tsx). `pick` поэтому задаёт не индекс карточки, а то, какой
 * по значению (`data-value`, см. QuestionFlow.tsx) вариант выбрать — "min"/"max" работают
 * одинаково вне зависимости от того, сколько у вопроса вариантов и куда направлен его ключ.
 */
export async function answerCurrentQuestion(page: Page, pick: "min" | "max" = "min") {
  const previousQuestion = await page.locator(".card h2").first().innerText();
  const numericInput = page.locator('.vas-input input[type="range"]');

  if (await numericInput.count()) {
    const value = pick === "min" ? 0 : 100;
    await numericInput.evaluate((el: HTMLInputElement, v: string) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
      setter.call(el, v);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }, String(value));
    await page.getByRole("button", { name: "Сохранить ответ" }).click();
  } else {
    const options = page.locator(".option-card");
    const count = await options.count();
    const values = await Promise.all(
      Array.from({ length: count }, (_, i) => options.nth(i).getAttribute("data-value")),
    );
    const numericValues = values.map(Number);
    const target = pick === "min" ? Math.min(...numericValues) : Math.max(...numericValues);
    await options.nth(numericValues.indexOf(target)).click();
  }

  // .first() — целевой экран после ответа не всегда один вопрос: последний ответ на этапе
  // переводит либо на следующий этап, либо на отчёт (несколько .card-секций сразу).
  await expect(page.locator(".card h2").first()).not.toHaveText(previousQuestion);
}

/**
 * Проходит этап целиком. `pick="min"` выбирает на каждом вопросе вариант с наименьшим
 * `data-value` (0 для EQ-5D VAS, минимальный ключ для карточек), `pick="max"` — с наибольшим.
 * Поскольку у HADS/Спилбергера–Ханина высокий балл = хуже, а у EQ-5D VAS высокий балл = лучше,
 * пара вызовов "min" на входном + "max" на итоговом (или наоборот) всегда даёт разнонаправленную
 * динамику — 4 "тревожных" показателя меняются в одну сторону, EQ-5D VAS в противоположную —
 * независимо от того, как именно реверсивны конкретные пункты HADS/СШХ.
 */
export async function completeStage(page: Page, pick: "min" | "max" = "min") {
  const followupButton = page.getByRole("button", { name: "Перейти к итоговым тестам" });
  if (await followupButton.isVisible()) await followupButton.click();
  await dismissStageIntro(page); // предыдущий этап мог завершиться стартовым экраном следующего
  const stageRoot = page.locator("[data-stage]").first();
  const targetStage = await stageRoot.getAttribute("data-stage");
  if (!targetStage) throw new Error("The current testing stage is missing.");
  const report = page.locator(".report-grid");
  const progress = page.locator(".progress-track");
  const menu = page.locator(".test-menu");
  const nextScreen = report.or(followupButton).or(progress).or(menu);

  for (let safety = 0; safety < 20; safety += 1) {
    await expect(nextScreen.first()).toBeVisible();
    if ((await report.isVisible()) || (await followupButton.isVisible())) return;
    if (await progress.isVisible()) {
      const total = await readTotalQuestions(page);
      const answeredAttribute = await page.locator("[data-answered-count]").getAttribute("data-answered-count");
      const answered = Number(answeredAttribute ?? 0);
      for (let i = answered; i < total; i += 1) await answerCurrentQuestion(page, pick);
      continue;
    }

    await expect(menu).toBeVisible();
    const menuStage = await menu.locator("xpath=..").getAttribute("data-stage");
    if (menuStage !== targetStage) return;
    const unfinished = page.locator('.test-menu__item[data-completed="false"]').first();
    if (!(await unfinished.count())) throw new Error(`No unfinished questionnaire remains in stage ${targetStage}.`);
    await unfinished.click();
  }
  throw new Error(`Stage ${targetStage} did not complete within the expected questionnaire count.`);
}
