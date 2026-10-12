import type { Page } from "@playwright/test";

/**
 * Надёжная проверка отсутствия горизонтального переполнения на мобильном экране.
 *
 * `document.documentElement.scrollWidth - clientWidth` — стандартный способ, но в headless
 * Chromium под mobile-эмуляцией он даёт ложное срабатывание: вертикальный скроллбар здесь
 * резервирует место (а не накладывается поверх контента, как на реальном мобильном браузере),
 * и тогда scrollWidth всегда больше clientWidth ровно на ширину скроллбара — даже если ни один
 * элемент реально не вылезает за пределы экрана. Поэтому проверяем конкретные элементы: есть ли
 * среди них хоть один, чей правый край выходит за видимую (без скроллбара) ширину окна —
 * per-element bounding rect не зависит от того, зарезервирован скроллбар или наложен поверх.
 */
export async function hasHorizontalOverflow(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const elements = document.querySelectorAll("body *");
    for (const el of elements) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.right > viewportWidth + 1) {
        return true;
      }
    }
    return false;
  });
}
