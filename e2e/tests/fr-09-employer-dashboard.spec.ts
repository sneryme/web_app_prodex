import { test } from "@playwright/test";
import { scenario } from "./support/scenario";

test.describe("FR-09 Employer dashboard", () => {
  scenario("FR-09.1", "аноним перенаправляется на вход, дашборд доступен только координатору/HR");
  scenario("FR-09.2", "видны охват, completion, 5 групповых показателей, распределения и сравнение «вход / итог»");
  scenario("FR-09.3", "фильтр по потоку меняет отображаемые данные");
  scenario("FR-09.4", "группа меньше порога публикации скрыта");
  scenario("FR-09.5", "в интерфейсе и ответах API нет индивидуальных строк, токенов и ответов");
});
