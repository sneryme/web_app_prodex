import { test } from "@playwright/test";
import { scenario } from "./support/scenario";

test.describe("FR-11 PRODEX Admin", () => {
  scenario("FR-11.1", "доступ только у PRODEX account; работодатель получает отказ");
  scenario("FR-11.2", "таблица клиентов со статусами и фильтрами");
  scenario("FR-11.3", "лицензия: одно юрлицо, срок 12 месяцев, статус истечения");
  scenario("FR-11.4", "видны потоки, completion, активность, ошибки и технические метрики");
  scenario("FR-11.5", "индивидуальных психологических результатов в админке нет");
  scenario("FR-11.6", "интерфейс отделён от employer dashboard");
});
