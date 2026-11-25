import { useState } from "react";
import { ApiError } from "../api";
import type { ParticipantHomeState } from "../types";

interface Props {
  home: ParticipantHomeState;
  onSelect: (bundleId: number) => Promise<void>;
}

export function BundleSelectionScreen({ home, onSelect }: Props) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(bundleId: number) {
    setBusyId(bundleId);
    setError(null);
    try {
      await onSelect(bundleId);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not open this test bundle. Please try again.");
      setBusyId(null);
    }
  }

  const statusLabel = (status: string) => {
    if (status === "completed") return "\u0417\u0430\u0432\u0435\u0440\u0448\u0451\u043d";
    if (status === "in_progress") return "\u0412 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u0435";
    return "\u041d\u0435 \u043d\u0430\u0447\u0430\u0442";
  };

  return (
    <section className="card">
      <span className="tag">{"\u0423\u0447\u0430\u0441\u0442\u0438\u0435 \u0432 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435"}</span>
      <h2>{"\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442 \u0442\u0435\u0441\u0442\u043e\u0432"}</h2>
      {home.is_test && <p><strong>Тестовый участник.</strong> Итоговое тестирование доступно без ожидания 7 дней.</p>}
      {home.bundles.length ? (
        <div className="bundle-menu">
          {home.bundles.map((bundle) => (
            <button
              key={bundle.id}
              type="button"
              className="bundle-menu__item"
              data-bundle-code={bundle.code}
              disabled={busyId !== null}
              onClick={() => void choose(bundle.id)}
            >
              <span className="bundle-menu__heading">
                <span className="bundle-menu__name">{bundle.name}</span>
                <span className={`bundle-menu__status bundle-menu__status--${bundle.status}`}>
                  {busyId === bundle.id ? "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430\u2026" : statusLabel(bundle.status)}
                </span>
              </span>
              <span className="bundle-menu__details">
                {"\u0412\u0445\u043e\u0434\u043d\u043e\u0439 \u044d\u0442\u0430\u043f"}: {bundle.baseline.answered}/{bundle.baseline.total}
                {" \u00b7 \u0418\u0442\u043e\u0433\u043e\u0432\u044b\u0439 \u044d\u0442\u0430\u043f"}: {bundle.followup.answered}/{bundle.followup.total}
              </span>
              <span className="bundle-menu__action">
                {bundle.status === "completed"
                  ? "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 \u00b7 \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e\u0435 \u043f\u0440\u043e\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e"
                  : bundle.status === "in_progress"
                    ? "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"
                    : "\u041d\u0430\u0447\u0430\u0442\u044c"}
              </span>
              <span className="bundle-menu__tests">
                {bundle.questionnaires.map((questionnaire) => (
                  <span key={questionnaire.code} className="bundle-menu__test">
                    {questionnaire.name}: {questionnaire.baseline_answered}/{questionnaire.question_count} · {questionnaire.followup_answered}/{questionnaire.question_count}
                  </span>
                ))}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <p>{"\u0414\u043b\u044f \u0432\u0430\u0448\u0435\u0439 \u043e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0446\u0438\u0438 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u043e\u0432. \u041e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043a \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443."}</p>
      )}
      {error && <p className="error-banner" role="alert">{error}</p>}
    </section>
  );
}
