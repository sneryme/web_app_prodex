import { useState } from "react";
import { submitAnswer } from "../api";
import type { SessionState } from "../types";
import { TokenBadge } from "./TokenBadge";

interface Props {
  session: SessionState;
  onAdvance: (session: SessionState) => void;
}

function initialIndex(session: SessionState): number {
  const firstUnanswered = session.questions.findIndex((question) => question.answer === null);
  return firstUnanswered === -1 ? Math.max(0, session.questions.length - 1) : firstUnanswered;
}

/**
 * ТЗ FR-06: один вопрос на экран, прогресс, автосохранение.
 * Родитель монтирует компонент заново при смене этапа (key={session.stage}), поэтому
 * при переходе входное → итоговое индекс вопроса сам пересчитывается с нуля.
 */
export function QuestionFlow({ session, onAdvance }: Props) {
  const [index, setIndex] = useState(() => initialIndex(session));
  const [pending, setPending] = useState<{ questionId: number; optionId: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const question = session.questions[index];
  const total = session.questions.length;
  const stageLabel = session.stage === "baseline" ? "Входное тестирование" : "Итоговое тестирование";
  const selectedOptionId =
    pending && pending.questionId === question.id ? pending.optionId : question.answer?.option_id ?? null;
  const canGoNext = index < total - 1 && question.answer !== null;

  async function selectOption(optionId: number) {
    const wasUnanswered = question.answer === null;
    setPending({ questionId: question.id, optionId });
    setSaving(true);
    setError(null);
    try {
      const updated = await submitAnswer(session.token, { question_id: question.id, option_id: optionId });
      setSaving(false);
      setPending(null);
      onAdvance(updated);
      // Автопереход вперёд — только когда отвечаем на новый вопрос, а не правим прошлый (FR-06.5).
      if (wasUnanswered && index < total - 1) {
        setIndex((current) => current + 1);
      }
    } catch {
      // ТЗ FR-06.7: при потере сети ответ не теряется — карточка остаётся выбранной, доступен повтор.
      setSaving(false);
      setError("Не удалось сохранить ответ. Проверьте соединение и повторите попытку.");
    }
  }

  function retry() {
    if (pending) void selectOption(pending.optionId);
  }

  return (
    <section className="card">
      <span className="tag">
        {stageLabel} · Вопрос {index + 1} из {total}
      </span>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${total ? (session.progress.answered / total) * 100 : 0}%` }}
        />
      </div>
      <h2>{question.text}</h2>
      {error && (
        <p className="error-banner">
          {error}{" "}
          <button type="button" className="link-button" onClick={retry}>
            Повторить
          </button>
        </p>
      )}
      <div className="option-grid">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            disabled={saving}
            className={option.id === selectedOptionId ? "option-card selected" : "option-card"}
            onClick={() => void selectOption(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="actions">
        <button type="button" className="ghost" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          Назад
        </button>
        <button type="button" className="ghost" disabled={!canGoNext} onClick={() => setIndex((i) => i + 1)}>
          Далее
        </button>
      </div>
      <TokenBadge token={session.token} />
    </section>
  );
}
