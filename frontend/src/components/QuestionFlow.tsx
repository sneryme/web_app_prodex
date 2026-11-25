import { useEffect, useState } from "react";
import { ApiError, submitAnswer } from "../api";
import type { SessionState } from "../types";

interface Props {
  session: SessionState;
  questionnaireCode: string;
  onAdvance: (session: SessionState) => void;
  onBackToMenu: (session: SessionState) => void;
  onQuestionnaireComplete: (session: SessionState) => void;
}

function initialIndex(questions: SessionState["questions"]): number {
  const firstUnanswered = questions.findIndex((question) => question.answer === null);
  return firstUnanswered === -1 ? Math.max(0, questions.length - 1) : firstUnanswered;
}

/**
 * ТЗ FR-06: один вопрос на экран, прогресс, автосохранение.
 * Родитель монтирует компонент заново при выборе теста и смене этапа.
 */
export function QuestionFlow({ session, questionnaireCode, onAdvance, onBackToMenu, onQuestionnaireComplete }: Props) {
  const questions = session.questions.filter((item) => item.questionnaire_code === questionnaireCode);
  const questionnaire = session.questionnaires.find((item) => item.code === questionnaireCode);
  const [index, setIndex] = useState(() => initialIndex(questions));
  const [pending, setPending] = useState<{ questionId: number; optionId: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const question = questions[index];
  const total = questions.length;
  const stageLabel = session.stage === "baseline" ? "Входное тестирование" : "Итоговое тестирование";
  const selectedOptionId =
    pending && pending.questionId === question.id ? pending.optionId : question.answer?.option_id ?? null;
  const canGoNext = index < total - 1 && question.answer !== null;
  const isNumeric = question.options.length === 0;
  // По умолчанию 0, а не середина шкалы — середина выглядела как уже осознанно выбранный ответ,
  // из-за чего участники пропускали вопрос, не подвинув ползунок (см. подсказку под ним).
  const [vasValue, setVasValue] = useState(() => Number(question.answer?.raw_value ?? 0));

  // Компонент не размонтируется между вопросами одного этапа (только между этапами, см. App.tsx),
  // поэтому при переходе к другому числовому вопросу ползунок нужно синхронизировать явно.
  useEffect(() => {
    if (isNumeric) setVasValue(Number(question.answer?.raw_value ?? 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id]);

  async function selectOption(optionId: number) {
    const stage = session.stage;
    if (!stage) return;
    const wasUnanswered = question.answer === null;
    setPending({ questionId: question.id, optionId });
    setSaving(true);
    setError(null);
    try {
      const updated = await submitAnswer(session.token, { bundle_id: session.bundle_id ?? 0, stage, question_id: question.id, option_id: optionId });
      setSaving(false);
      setPending(null);
      const isQuestionnaireComplete = updated.questions.filter((item) => item.questionnaire_code === questionnaireCode).every((item) => item.answer !== null);
      if (updated.stage !== session.stage || isQuestionnaireComplete) onQuestionnaireComplete(updated);
      else onAdvance(updated);
      // Автопереход вперёд — только когда отвечаем на новый вопрос, а не правим прошлый (FR-06.5).
      if (wasUnanswered && index < total - 1) {
        setIndex((current) => current + 1);
      }
    } catch (error) {
      // ТЗ FR-06.7: при потере сети ответ не теряется — карточка остаётся выбранной, доступен повтор.
      setSaving(false);
      setError(error instanceof ApiError ? error.message : "Не удалось сохранить ответ. Проверьте соединение и повторите попытку.");
    }
  }

  async function submitVas() {
    const stage = session.stage;
    if (!stage) return;
    const wasUnanswered = question.answer === null;
    setSaving(true);
    setError(null);
    try {
      const updated = await submitAnswer(session.token, { bundle_id: session.bundle_id ?? 0, stage, question_id: question.id, raw_value: String(vasValue) });
      setSaving(false);
      const isQuestionnaireComplete = updated.questions.filter((item) => item.questionnaire_code === questionnaireCode).every((item) => item.answer !== null);
      if (updated.stage !== session.stage || isQuestionnaireComplete) onQuestionnaireComplete(updated);
      else onAdvance(updated);
      if (wasUnanswered && index < total - 1) {
        setIndex((current) => current + 1);
      }
    } catch (error) {
      setSaving(false);
      setError(error instanceof ApiError ? error.message : "Не удалось сохранить ответ. Проверьте соединение и повторите попытку.");
    }
  }

  function retry() {
    if (pending) void selectOption(pending.optionId);
    else if (isNumeric) void submitVas();
  }

  return (
    <section
      className="card"
      data-stage={session.stage ?? ""}
      data-question-count={total}
      data-answered-count={questionnaire?.answered_count ?? 0}
      data-questionnaire-code={questionnaireCode}
    >
      <span className="tag">
        {questionnaire?.name ?? stageLabel} · Вопрос {index + 1} из {total}
      </span>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${total ? (questions.filter((item) => item.answer !== null).length / total) * 100 : 0}%` }}
        />
      </div>
      <h2>{question.text}</h2>
      {session.is_test && <p className="hint">Тестовый участник · результаты не входят в групповую статистику.</p>}
      {session.methodology === "iipb-0.1" && <p className="hint">{
        questionnaireCode === "hads" ? "Оцените самочувствие за последнюю неделю." :
        question.indicator_code === "situational_anxiety" ? "Отвечайте о том, как вы чувствуете себя в данный момент." :
        question.indicator_code === "trait_anxiety" ? "Отвечайте о том, как вы чувствуете себя обычно." :
        "Оцените состояние своего здоровья сегодня."
      }</p>}
      {error && (
        <p className="error-banner">
          {error}{" "}
          <button type="button" className="link-button" onClick={retry}>
            Повторить
          </button>
        </p>
      )}
      {isNumeric ? (
        <div className="vas-input">
          <p className="hint">Передвиньте ползунок, чтобы указать значение от 0 до 100</p>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={vasValue}
            disabled={saving}
            onChange={(event) => setVasValue(Number(event.target.value))}
          />
          <div className="vas-value">{vasValue}</div>
          <button type="button" disabled={saving} onClick={() => void submitVas()}>
            Сохранить ответ
          </button>
        </div>
      ) : (
        <div className="option-grid">
          {question.options.map((option) => (
            <button
              key={option.id}
              type="button"
              disabled={saving}
              data-value={option.value}
              className={option.id === selectedOptionId ? "option-card selected" : "option-card"}
              onClick={() => void selectOption(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
      <div className="actions">
        <button type="button" className="ghost" disabled={saving} onClick={() => onBackToMenu(session)}>
          К меню
        </button>
        <button type="button" className="ghost" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          Назад
        </button>
        <button type="button" className="ghost" disabled={!canGoNext} onClick={() => setIndex((i) => i + 1)}>
          Далее
        </button>
      </div>
    </section>
  );
}
