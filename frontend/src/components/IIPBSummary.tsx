import type { IIPBDynamics, IIPBMeasurement, RoutingContacts } from "../types";

const format = (value: number) => value.toLocaleString("ru-RU", { maximumFractionDigits: 1 });

function Measurement({ title, result }: { title: string; result: IIPBMeasurement }) {
  return (
    <article className={`iipb-measurement iipb-level--${result.level}`}>
      <h3>{title}</h3>
      <p className="iipb-date">{new Date(result.measured_at).toLocaleDateString("ru-RU")}</p>
      <div className="iipb-value">{result.index}<span>%</span></div>
      <meter className="iipb-meter" min={0} max={100} value={result.index} aria-label={`ИИПБ: ${result.index}%`} />
      <p>Уровень {result.level} · {result.level_label}</p>
      <div className={result.red_flags.length ? "iipb-alert iipb-alert--red" : "iipb-conclusion"}>
        <strong>{result.conclusion}</strong>
        <p>{result.action}</p>
      </div>
      {result.red_flags.map((flag) => <p className="iipb-flag iipb-flag--red" key={flag.code}><strong>{flag.code}</strong> · {flag.label}</p>)}
      {result.yellow_flags.map((flag) => <div className="iipb-alert iipb-alert--yellow" key={flag.code}><strong>{flag.code} · {flag.label}</strong><p>{flag.action}</p></div>)}
      {!result.red_flags.length && !result.yellow_flags.length && <p>Красных и жёлтых флагов нет.</p>}
      <p>Личностная тревожность: <strong>{result.trait_marker.raw_score} · {result.trait_marker.label}</strong>. Фоновый маркер; в индекс и динамику не входит.</p>
      <details className="iipb-details">
        <summary>Из чего складывается индекс</summary>
        <dl>
          <dt>Тревога</dt><dd>{format(result.domains.anxiety)}%</dd>
          <dt>Депрессия</dt><dd>{format(result.domains.depression)}%</dd>
          <dt>Самочувствие / здоровье</dt><dd>{format(result.domains.health)}%</dd>
          <dt>Сумма уровней EQ-5D-5L</dt><dd>{result.lss}</dd>
        </dl>
        <p>Три домена имеют равный вес. Подындексы и домены при расчёте не округляются.</p>
      </details>
    </article>
  );
}

export function IIPBSummary({ baseline, followup, dynamics, contacts }: {
  baseline: IIPBMeasurement;
  followup?: IIPBMeasurement | null;
  dynamics?: IIPBDynamics | null;
  contacts?: RoutingContacts;
}) {
  const results = [baseline, ...(followup ? [followup] : [])];
  const needsSpecialist = results.some(r => r.red_flags.length || ["III", "IV"].includes(r.level) || r.yellow_flags.some(f => f.code === "Y1")) || dynamics?.actions.some(action => /специалист|психотерапевт|психиатр|психолог/.test(action));
  const needsPhysician = results.some(r => r.yellow_flags.some(f => f.code === "Y2" || f.code === "Y3"));
  return (
    <section className="card iipb-summary" aria-label="Результат ИИПБ">
      <span className="tag">Психоэмоциональное благополучие · ИИПБ v{baseline.version}</span>
      <h2>{followup ? "Ваше состояние до и после курса" : "Ваш входной результат"}</h2>
      <p>{baseline.notice}</p>
      <div className="iipb-measurements">
        <Measurement title="До курса" result={baseline} />
        {followup && <Measurement title="После курса" result={followup} />}
      </div>
      {dynamics && <div className="iipb-dynamics">
        <h3>Изменение ИИПБ</h3>
        <strong className="iipb-delta">{dynamics.delta_pp > 0 ? "+" : ""}{dynamics.delta_pp} п.п.</strong>
        <p>{dynamics.delta_percent === null ? "Относительное изменение не рассчитывается: исходный индекс равен 0." : `${dynamics.delta_percent > 0 ? "+" : ""}${format(dynamics.delta_percent)}% от исходного значения`} · уровень {dynamics.level_change}</p>
        <p>{dynamics.notice}</p>
        {dynamics.actions.map(action => <p className="iipb-alert iipb-alert--yellow" key={action}>{action}</p>)}
      </div>}
      {(needsSpecialist || needsPhysician) && <div className="iipb-contacts">
        <h3>К кому обратиться</h3>
        {needsSpecialist && <p><strong>Специалист:</strong> {contacts?.specialist || "Контакты врача-психотерапевта, врача-психиатра или медицинского психолога уточните у координатора программы."}</p>}
        {needsPhysician && <p><strong>Терапевт:</strong> {contacts?.physician || "Контакты терапевта уточните у координатора программы."}</p>}
      </div>}
      <p className="note">Методология от {new Date(`${baseline.version_date}T00:00:00`).toLocaleDateString("ru-RU")}. Индивидуальный результат доступен вам; работодатель видит только групповые данные.</p>
    </section>
  );
}
