import { test } from "@playwright/test";

/**
 * Сценарий из project/TEST_SCENARIOS.md, который ещё нельзя автоматизировать:
 * функциональность не реализована. Playwright показывает такие тесты как
 * «skipped», а ID связывает их с требованием ТЗ.
 *
 * Когда функциональность появится, замените `scenario(...)` на `test(...)`
 * с реальными шагами и обновите статус в TEST_SCENARIOS.md.
 */
export function scenario(id: string, title: string): void {
  test.fixme(`${id} ${title}`, async () => {});
}
