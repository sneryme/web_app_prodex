import type { SessionState } from "../types";

interface Props {
  session: SessionState;
  onSelect: (code: string) => void;
  onBackToBundles: () => void;
}

/** Главное меню маршрута. Список берётся из активного комплекта тестов API. */
export function TestMenuScreen({ session, onSelect, onBackToBundles }: Props) {
  const stageName = session.stage === "baseline" ? "Входное тестирование" : "Итоговое тестирование";
  const completed = session.questionnaires.filter((item) => item.answered_count === item.question_count).length;
  const isIIPB = session.methodology === "iipb-0.1";
  const nextCode = session.questionnaires.find(item => item.answered_count < item.question_count)?.code;

  return (
    <section className="card" data-stage={session.stage ?? ""}>
      <span className="tag">{stageName}</span>
      {session.is_test && <p><strong>Тестовый участник.</strong> Данные используются для проверки сайта и не входят в групповую статистику.</p>}
      <h2>{completed ? "Продолжить тестирование" : "Главное меню"}</h2>
      <p>{isIIPB ? "Пройдите опросники последовательно: HADS, Спилбергер–Ханин, EQ-5D-5L. Все вопросы обязательны." : completed ? "Выберите следующий тест или продолжите начатый." : "Выберите тест, чтобы начать."}</p>
      {isIIPB && session.stage === "baseline" && <p>Пройдите входное тестирование до первой процедуры: в день начала курса или накануне.</p>}
      <div className="test-menu">
        {session.questionnaires.map((item) => {
          const isComplete = item.answered_count === item.question_count;
          return (
            <button
              key={item.code}
              type="button"
              className="test-menu__item"
              data-questionnaire-code={item.code}
              data-completed={isComplete ? "true" : "false"}
              disabled={isComplete || (isIIPB && item.code !== nextCode)}
              onClick={() => onSelect(item.code)}
            >
              <span className="test-menu__name">{item.name}</span>
              <span className="test-menu__status">
                {isComplete ? "Завершён" : isIIPB && item.code !== nextCode ? "После предыдущего опросника" : item.answered_count ? `Продолжить · ${item.answered_count}/${item.question_count}` : `${item.question_count} вопросов`}
              </span>
            </button>
          );
        })}
      </div>
      <button type="button" className="ghost" onClick={onBackToBundles}>
        {"\u0412\u044b\u0431\u0440\u0430\u0442\u044c \u0434\u0440\u0443\u0433\u043e\u0439 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442"}
      </button>
    </section>
  );
}
