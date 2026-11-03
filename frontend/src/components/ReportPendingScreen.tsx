/** ТЗ FR-04.4: токен с завершёнными этапами открывает отчёт, а не повторное тестирование.
 *  Сам отчёт (FR-08) — следующий шаг; пока показываем понятную заглушку вместо вопросов. */
export function ReportPendingScreen({ onBackToBundles }: { onBackToBundles: () => void }) {
  return (
    <section className="card">
      <span className="tag">Спасибо</span>
      <h2>Вы прошли оба этапа тестирования</h2>
      <p>Персональный отчёт «до / после» появится здесь, когда в сервисе будет включён расчёт результатов.</p>
      <button type="button" className="ghost" onClick={onBackToBundles}>
        {"\u0412 \u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e \u043a \u0432\u044b\u0431\u043e\u0440\u0443 \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u043e\u0432"}
      </button>
    </section>
  );
}
