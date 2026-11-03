import { useEffect, useState } from "react";
import { getReport } from "../api";
import type { PersonalReport } from "../types";
import { ReportPendingScreen } from "./ReportPendingScreen";

const TREND_LABEL: Record<string, string> = {
  improved: "улучшение",
  worsened: "ухудшение",
  stable: "без изменений",
};

interface Props {
  token: string;
  bundleId: number;
  onBackToBundles: () => void;
}

/** ТЗ FR-08: персональный отчёт «до/после». Пока отчёт не готов — показываем понятную заглушку. */
export function ReportScreen({ token, bundleId, onBackToBundles }: Props) {
  const [report, setReport] = useState<PersonalReport | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "pending">("loading");

  useEffect(() => {
    let cancelled = false;
    getReport(token, bundleId)
      .then((data) => {
        if (!cancelled) {
          setReport(data);
          setStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("pending");
      });
    return () => {
      cancelled = true;
    };
  }, [token, bundleId]);

  if (status === "loading") {
    return (
      <section className="card">
        <span className="tag">Загрузка</span>
        <h2>Секунду…</h2>
        <p>Считаем ваш результат.</p>
        <button type="button" className="ghost" onClick={onBackToBundles}>
          {"\u0412 \u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e \u043a \u0432\u044b\u0431\u043e\u0440\u0443 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u043e\u0432"}
        </button>
      </section>
    );
  }

  if (status === "pending" || report === null) {
    return <ReportPendingScreen onBackToBundles={onBackToBundles} />;
  }

  return (
    <>
      <section className="card">
        <span className="tag">Ваши результаты после курса</span>
        <h2>
          {report.improved_count > 0
            ? `Положительная динамика по ${report.improved_count} из ${report.total_count} показателей`
            : "Результаты после курса"}
        </h2>
        <p>{report.summary}</p>
      </section>

      <section className="card">
        <h2>Динамика по показателям</h2>
        <div className="report-grid">
          {report.cards.map((card) => (
            <article key={card.indicator_code} className={`report-card report-card--${card.trend}`}>
              <h3>{card.label}</h3>
              <div className="report-card__values">
                <span>{card.before.raw_score}</span>
                <span className="report-card__arrow">→</span>
                <span>{card.after.raw_score}</span>
              </div>
              <p className="report-card__zones">
                {card.before.zone} → {card.after.zone}
              </p>
              <p className="report-card__trend">{TREND_LABEL[card.trend] ?? card.trend}</p>
            </article>
          ))}
        </div>
      </section>

      {report.eq5d_profile.length > 0 && (
        <section className="card">
          <h2>Ваш профиль здоровья (EQ-5D)</h2>
          <p>Дополнительные измерения EQ-5D — не входят в 5 основных показателей выше.</p>
          <ul className="facts">
            {report.eq5d_profile.map((item) => (
              <li key={item.indicator_code}>
                <strong>{item.label}:</strong> {item.before} → {item.after}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="card">
        <button type="button" className="ghost" onClick={onBackToBundles}>
          {"\u0412 \u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e \u043a \u0432\u044b\u0431\u043e\u0440\u0443 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u043e\u0432"}
        </button>
      </section>
    </>
  );
}
