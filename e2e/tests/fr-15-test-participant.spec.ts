import { expect, test } from "@playwright/test";

const token = process.env.E2E_TEST_PARTICIPANT_TOKEN;

test("Тестовый участник начинает итоговый этап без семидневного ожидания", async ({ page, isMobile }, info) => {
  test.skip(!token, "Нужен новый код из команды create_test_participant в E2E_TEST_PARTICIPANT_TOKEN");
  test.skip(isMobile, "Для каждого запуска нужен отдельный свежий тестовый участник");
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\//, route => route.abort());
  await page.goto(`/?token=${encodeURIComponent(token!)}`);
  await page.locator('[data-bundle-code="iipb-0.1"]').click();
  await page.getByRole("button", { name: "Начать знакомство" }).click();
  await page.getByLabel(/Мне исполнилось 18 лет/).check();
  await page.getByLabel(/Я ознакомлен\(а\)/).check();
  await page.getByLabel(/Я согласен\(на\) на обработку сведений/).check();
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await expect(page.locator(".iipb-value")).toHaveText("66%");
  const next = page.getByRole("button", { name: "Перейти к итоговым тестам" });
  await expect(next).toBeEnabled();
  await expect(page.getByText("Итоговый тест можно пройти сразу.", { exact: false })).toBeVisible();
  await next.click();
  await page.locator('.test-menu__item[data-questionnaire-code="hads"]').click();
  await expect(page.locator('[data-stage="followup"]')).toBeVisible();
  const before = await page.locator(".card h2").innerText();
  await page.locator('.option-card[data-value="0"]').click();
  await expect(page.locator(".card h2")).not.toHaveText(before);
  await page.reload();
  await page.locator('[data-bundle-code="iipb-0.1"]').click();
  await expect(page.locator('[data-stage="followup"][data-answered-count="1"]')).toBeVisible();
  await expect(page.getByText("Тестовый участник · результаты не входят в групповую статистику.")).toBeVisible();
  await page.screenshot({ path: info.outputPath("test-followup.png"), fullPage: true });
});
