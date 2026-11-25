import { expect, test } from "@playwright/test";

test("Демодашборд ИИПБ показывает 8 пар и скрывает показатели группы из 3 человек", async ({ page }) => {
  const password = process.env.IIPB_DEMO_STAFF_PASSWORD;
  if (!password) throw new Error("Задайте IIPB_DEMO_STAFF_PASSWORD и выполните seed_iipb_demo.");
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\//, route => route.abort());
  await page.goto("/employer");
  await page.getByLabel("Логин").fill("iipb_demo");
  await page.getByLabel("Пароль").fill(password);
  await page.getByRole("button", { name: "Войти" }).click();

  const stream = page.getByRole("combobox", { name: "Поток", exact: true });
  const card = page.getByRole("region", { name: "Групповой ИИПБ" });
  const summary = page.locator(".employer-stat__value");
  await stream.selectOption({ label: "Основная группа" });
  await expect(summary).toHaveText(["8", "8", "8"]);
  await expect(card.getByText(/Пар: 8/)).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Скачать XLSX" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);

  await stream.selectOption({ label: "Пилотная группа" });
  await expect(summary).toHaveText(["3", "3", "3"]);
  await expect(card.getByText(/Недостаточно замеров для публикации \(n=3\)/)).toHaveCount(2);
  await expect(card.locator(".employer-mean")).toHaveCount(0);
});
