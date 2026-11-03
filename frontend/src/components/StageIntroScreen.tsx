import type { SessionState } from "../types";

interface Props {
  session: SessionState;
  onStart: () => void;
}

/**
 * Стартовый экран этапа: тест не начинается сразу после согласия/перехода к следующему этапу —
 * участник сам нажимает «Начать», когда готов. После завершения входного этапа тот же экран
 * показывается перед итоговым, с другой формулировкой («входной этап завершён»).
 */
export function StageIntroScreen({ session, onStart }: Props) {
  const isFollowup = session.stage === "followup";

  return (
    <section className="card">
      <span className="tag">{isFollowup ? "Итоговое тестирование" : "Входное тестирование"}</span>
      <h2>{isFollowup ? "Тест завершён" : "Готовы начать?"}</h2>
      {isFollowup ? (
        <p>Вы прошли входной этап. Для прохождения итогового теста нажмите сюда.</p>
      ) : (
        <p>
          Сейчас начнётся тестирование — один вопрос на экран, ответы сохраняются автоматически.
          Прохождение займёт несколько минут.
        </p>
      )}
      <button type="button" onClick={onStart}>
        {isFollowup ? "Начать итоговое тестирование" : "Начать тестирование"}
      </button>
    </section>
  );
}
