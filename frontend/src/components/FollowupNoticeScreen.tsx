import type { SessionState } from "../types";
import { IIPBSummary } from "./IIPBSummary";
import { TokenBadge } from "./TokenBadge";

interface Props {
  session: SessionState;
  onContinue: () => void;
  onBackToBundles: () => void;
}

export function FollowupNoticeScreen({ session, onContinue, onBackToBundles }: Props) {
  const needsConsultation = session.baseline_result && (session.baseline_result.red_flags.length > 0 || session.baseline_result.level === "IV");
  return <>
    {session.baseline_result && <IIPBSummary baseline={session.baseline_result} contacts={session.routing_contacts} />}
    <section className="card">
      <span className="tag">Входной этап завершён</span>
      <h2>{needsConsultation ? "Перед курсом обратитесь к специалисту" : "Перед итоговым тестированием пройдите курс"}</h2>
      {needsConsultation && <p>Консультация нужна до курса или вместо него. Решение о продолжении курса принимает специалист.</p>}
      <p>Пройдите итоговое тестирование после последней процедуры курса: в спокойной обстановке, примерно в то же время суток, вне сеанса и не сразу после него.</p>
      {session.is_test ? <p><strong>Тестовый участник.</strong> Итоговый тест можно пройти сразу. Эти результаты не входят в групповую статистику.</p> : session.followup_available_at && <p>Между замерами необходимо не менее 7 дней. Итоговое тестирование доступно с <strong>{new Date(session.followup_available_at).toLocaleString("ru-RU")}</strong>.</p>}
      <TokenBadge token={session.token} />
      <button type="button" disabled={session.followup_locked} onClick={onContinue}>
        {session.followup_locked ? "Ожидаем итоговый замер" : "Перейти к итоговым тестам"}
      </button>
      <div className="actions"><button type="button" className="ghost" onClick={onBackToBundles}>В главное меню</button></div>
    </section>
  </>;
}
