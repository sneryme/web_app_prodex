import type { IIPBOverview, StageBlock } from "./types";

function Measurement({ title, block }: { title: string; block: StageBlock }) {
  return <div className="employer-stage">
    <h3>{title}</h3>
    {block.is_suppressed ? <p className="employer-suppressed">Недостаточно замеров для публикации (n={block.participant_count}).</p> : <>
      <div className="employer-mean">{block.mean}%</div>
      <p>Медиана: {block.median}% · замеров: {block.participant_count}</p>
      <ul className="employer-distribution">{Object.entries(block.zone_distribution ?? {}).map(([label, count]) => <li key={label}><span>{label}</span><strong>{count}</strong></li>)}</ul>
      <p>С красными флагами: {block.red_flag_count}<br />С жёлтыми флагами: {block.yellow_flag_count}</p>
      <details><summary>Флаги и фоновый маркер ЛТ</summary>
        <ul className="employer-distribution">{Object.entries(block.flag_distribution ?? {}).map(([code, count]) => <li key={code}><span>{code}</span><strong>{count}</strong></li>)}</ul>
        <p>Личностная тревожность (в динамике не используется)</p>
        <ul className="employer-distribution">{Object.entries(block.trait_distribution ?? {}).map(([label, count]) => <li key={label}><span>{label}</span><strong>{count}</strong></li>)}</ul>
      </details>
    </>}
  </div>;
}

export function IIPBOverviewCard({ data }: { data: IIPBOverview }) {
  const trend = data.trend;
  return <section className="employer-card employer-iipb" aria-label="Групповой ИИПБ">
    <h2>Психоэмоциональное благополучие · ИИПБ v{data.version}</h2>
    <p>{data.notice}</p>
    <div className="employer-card__stages"><Measurement title="До курса" block={data.baseline} /><Measurement title="После курса" block={data.followup} /></div>
    <div className="employer-card__trend">
      {trend.is_suppressed ? <p className="employer-suppressed">Недостаточно пар для оценки динамики (n={trend.paired_count}). Порог публикации: {data.threshold}.</p> : <>
        <p><strong>Средняя Δ: {trend.mean_delta} п.п. · медианная Δ: {trend.median_delta} п.п.</strong></p>
        <p>Пар: {trend.paired_count} · улучшение: {trend.improved} · ухудшение: {trend.worsened} · без изменений: {trend.stable}</p>
      </>}
    </div>
    <p className="employer-footnote">{data.dynamics_notice} Статистика предназначена для наблюдения за программой и не применяется для кадровых решений или рейтингования подразделений.</p>
  </section>;
}
