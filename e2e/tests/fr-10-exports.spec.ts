import { test } from "@playwright/test";
import { scenario } from "./support/scenario";

test.describe("FR-10 Экспорт PDF/XLSX для работодателя", () => {
  scenario("FR-10.1", "PDF-отчёт скачивается и содержит только агрегаты");
  scenario("FR-10.2", "XLSX не содержит строк участников и токенов");
  scenario("FR-10.3", "малые группы скрыты и в экспорте");
  scenario("FR-10.4", "экспорт недоступен без прав координатора/HR");
});
