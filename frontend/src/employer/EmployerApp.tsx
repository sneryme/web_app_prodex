import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../httpClient";
import {
  clearSession,
  downloadExport,
  getBundles,
  getComparison,
  getOrganizations,
  getOverview,
  getStaffInfo,
  getStreams,
  getToken,
  login as loginRequest,
  logout as logoutRequest,
  setSession,
  type StaffInfo,
} from "./api";
import type { BundleSummary, ComparisonResult, OrganizationOverview, OrganizationSummary, StreamSummary } from "./types";
import { IIPBOverviewCard } from "./IIPBOverviewCard";

const TREND_LABEL: Record<string, string> = { improved: "Улучшение", worsened: "Ухудшение", stable: "Без изменений" };

/**
 * Дашборд работодателя (ТЗ FR-09). Отдельный контур от участника (PROJECT_RULES №9: desktop-first,
 * без mobile-ограничений основного styles.css) — собственный маршрут `/employer`, см. main.tsx.
 *
 * ТЗ FR-09.1/FR-12-lite: вход по логину/паролю (identity.StaffProfile, DRF TokenAuthentication) —
 * не полноценный RBAC из ТЗ FR-12 (нет ролевых ограничений на действия), только факт
 * "залогиненный сотрудник, а не аноним". Организация ограничивается на бэкенде по роли
 * (администратор организации видит только свою — apps/reporting/views.py::_visible_organizations).
 */
export function EmployerApp() {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [staff, setStaff] = useState<StaffInfo | null>(() => getStaffInfo());

  function handleLoggedIn(nextStaff: StaffInfo) {
    setStaff(nextStaff);
    setTokenState(getToken());
  }

  function handleSessionExpired() {
    clearSession();
    setTokenState(null);
    setStaff(null);
  }

  if (!token) {
    return <LoginScreen onLoggedIn={handleLoggedIn} />;
  }

  return <Dashboard staff={staff} onSessionExpired={handleSessionExpired} />;
}

function LoginScreen({ onLoggedIn }: { onLoggedIn: (staff: StaffInfo) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await loginRequest(username, password);
      setSession(response);
      onLoggedIn({ role_display: response.role_display, organization: response.organization });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось войти.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="employer-shell employer-shell--login">
      <form className="employer-login" onSubmit={handleSubmit}>
        <span className="employer-eyebrow">PRODEX / DIGITAL · Дашборд работодателя</span>
        <h1>Вход для администратора</h1>
        <label>
          Логин
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </label>
        <label>
          Пароль
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="employer-error">{error}</p>}
        <button type="submit" disabled={pending}>
          {pending ? "Входим…" : "Войти"}
        </button>
      </form>
    </div>
  );
}

function Dashboard({ staff, onSessionExpired }: { staff: StaffInfo | null; onSessionExpired: () => void }) {
  const [organizations, setOrganizations] = useState<OrganizationSummary[] | null>(null);
  const [organizationId, setOrganizationId] = useState<number | null>(null);
  const [streams, setStreams] = useState<StreamSummary[] | null>(null);
  const [streamId, setStreamId] = useState<number | null>(null);
  const [bundles, setBundles] = useState<BundleSummary[] | null>(null);
  const [bundleId, setBundleId] = useState<number | null>(null);
  const [overview, setOverview] = useState<OrganizationOverview | null>(null);
  const [dashboardMode, setDashboardMode] = useState<"overview" | "streams" | "periods">("overview");
  const [selectedStreamIds, setSelectedStreamIds] = useState<number[]>([]);
  const [periodAFrom, setPeriodAFrom] = useState("");
  const [periodATo, setPeriodATo] = useState("");
  const [periodBFrom, setPeriodBFrom] = useState("");
  const [periodBTo, setPeriodBTo] = useState("");
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const comparisonRequestId = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"pdf" | "xlsx" | "csv" | null>(null);

  function handleError(e: unknown, fallback: string) {
    if (e instanceof ApiError && e.status === 401) {
      onSessionExpired();
      return;
    }
    setError(e instanceof ApiError ? e.message : fallback);
  }

  useEffect(() => {
    let active = true;
    getOrganizations()
      .then((orgs) => {
        if (!active) return;
        setOrganizations(orgs);
        setOrganizationId((current) => current ?? orgs[0]?.id ?? null);
      })
      .catch((e) => {
        if (active) handleError(e, "Не удалось загрузить список организаций.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (organizationId === null) return;
    let active = true;
    getStreams(organizationId)
      .then((items) => {
        if (!active) return;
        setStreams(items);
        setSelectedStreamIds(items.slice(0, 2).map((item) => item.id));
        setComparison(null);
      })
      .catch((e) => {
        if (active) handleError(e, "Не удалось загрузить список потоков.");
      });
    return () => {
      active = false;
    };
  }, [organizationId]);

  useEffect(() => {
    if (organizationId === null) return;
    let active = true;
    getBundles(organizationId).then((items) => {
      if (!active) return;
      setBundles(items);
      setBundleId(items[0]?.id ?? null);
    }).catch((e) => {
      if (active) handleError(e, "Не удалось загрузить комплекты тестов.");
    });
    return () => {
      active = false;
    };
  }, [organizationId]);

  useEffect(() => {
    if (organizationId === null || bundles === null || dashboardMode !== "overview") return;
    getOverview(organizationId, streamId, bundleId)
      .then((data) => {
        setOverview(data);
        setError(null);
      })
      .catch((e) => handleError(e, "Не удалось загрузить агрегаты."));
  }, [organizationId, streamId, bundleId, bundles, dashboardMode]);

  async function handleCompare() {
    if (organizationId === null || bundles === null || dashboardMode === "overview") return;
    const requestId = ++comparisonRequestId.current;
    const requestedOrganizationId = organizationId;
    const requestedMode = dashboardMode;
    const params = new URLSearchParams({ mode: dashboardMode });
    if (dashboardMode === "streams") {
      if (selectedStreamIds.length < 2 || selectedStreamIds.length > 4) {
        setError("Выберите от 2 до 4 потоков для сравнения.");
        return;
      }
      params.set("streams", selectedStreamIds.join(","));
    } else {
      params.set("period_a_from", periodAFrom);
      params.set("period_a_to", periodATo);
      params.set("period_b_from", periodBFrom);
      params.set("period_b_to", periodBTo);
    }
    setComparing(true);
    setComparison(null);
    setError(null);
    try {
      const result = await getComparison(requestedOrganizationId, bundleId, params);
      if (requestId !== comparisonRequestId.current) return;
      if (result.groups.some((group) => group.overview.organization.id !== requestedOrganizationId)) {
        throw new Error("Сервер вернул данные другой организации. Обновите страницу и повторите запрос.");
      }
      if (requestedMode !== dashboardMode || requestedOrganizationId !== organizationId) return;
      setComparison(result);
    } catch (e) {
      if (requestId === comparisonRequestId.current) handleError(e, "Не удалось сравнить выбранные группы.");
    } finally {
      if (requestId === comparisonRequestId.current) setComparing(false);
    }
  }

  async function handleLogout() {
    try {
      await logoutRequest();
    } catch {
      // токен мог уже истечь/быть отозван — всё равно чистим локальную сессию
    }
    onSessionExpired();
  }

  async function handleExport(format: "pdf" | "xlsx" | "csv") {
    if (organizationId === null) return;
    setExporting(format);
    try {
      await downloadExport(organizationId, streamId, bundleId, format);
    } catch (e) {
      handleError(e, "Не удалось сформировать экспорт.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="employer-shell">
      <header className="employer-header">
        <div className="employer-header__top">
          <span className="employer-eyebrow">PRODEX / DIGITAL · Дашборд работодателя</span>
          <div className="employer-session">
            {staff && (
              <span className="employer-session__info">
                {staff.role_display}
                {staff.organization ? ` · ${staff.organization.name}` : ""}
              </span>
            )}
            <button type="button" className="employer-session__logout" onClick={handleLogout}>
              Выйти
            </button>
          </div>
        </div>
        <h1>Динамика по группе «до / после»</h1>
        <nav className="employer-view-mode" aria-label="Режим дашборда">
          <button type="button" aria-pressed={dashboardMode === "overview"} onClick={() => { comparisonRequestId.current += 1; setDashboardMode("overview"); setComparison(null); setComparing(false); setError(null); }}>
            Обзор
          </button>
          <button type="button" aria-pressed={dashboardMode === "streams"} onClick={() => { comparisonRequestId.current += 1; setDashboardMode("streams"); setComparison(null); setComparing(false); setError(null); }}>
            Сравнить потоки
          </button>
          <button type="button" aria-pressed={dashboardMode === "periods"} onClick={() => { comparisonRequestId.current += 1; setDashboardMode("periods"); setComparison(null); setComparing(false); setError(null); }}>
            Сравнить периоды
          </button>
        </nav>
        <div className="employer-filters">
          <label>
            Организация
            <select
              value={organizationId ?? ""}
              onChange={(e) => {
                comparisonRequestId.current += 1;
                setOrganizationId(Number(e.target.value));
                setStreamId(null);
                setStreams(null);
                setSelectedStreamIds([]);
                setBundles(null);
                setBundleId(null);
                setComparison(null);
                setComparing(false);
                setOverview(null);
              }}
              disabled={!organizations}
            >
              {(organizations ?? []).map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          </label>
          {dashboardMode === "overview" && <label>
            Поток
            <select
              value={streamId ?? "all"}
              onChange={(e) => setStreamId(e.target.value === "all" ? null : Number(e.target.value))}
              disabled={!streams}
            >
              <option value="all">Все потоки</option>
              {(streams ?? []).map((stream) => (
                <option key={stream.id} value={stream.id}>
                  {stream.name || `Поток ${stream.id}`}
                </option>
              ))}
            </select>
          </label>}
          <label>
            Комплект тестов
            <select
              value={bundleId ?? ""}
              onChange={(e) => {
                comparisonRequestId.current += 1;
                setBundleId(e.target.value ? Number(e.target.value) : null);
                setComparison(null);
                setComparing(false);
                setOverview(null);
              }}
              disabled={!bundles}
            >
              {(bundles ?? []).map((bundle) => (
                <option key={bundle.id} value={bundle.id}>{bundle.name}</option>
              ))}
            </select>
          </label>
          {dashboardMode === "overview" && <div className="employer-export">
            <button type="button" disabled={!overview || exporting !== null} onClick={() => handleExport("xlsx")}>
              {exporting === "xlsx" ? "Готовим…" : "Скачать XLSX"}
            </button>
            <button type="button" disabled={!overview || exporting !== null} onClick={() => handleExport("pdf")}>
              {exporting === "pdf" ? "Готовим…" : "Скачать PDF"}
            </button>
            <button type="button" disabled={!overview || exporting !== null} onClick={() => handleExport("csv")}>
              {exporting === "csv" ? "Готовим…" : "Скачать CSV"}
            </button>
          </div>}
          {dashboardMode === "overview" && <p className="employer-export__note">XLSX: отдельный лист для каждого показателя, зоны распределения вынесены в отдельные столбцы. CSV остаётся одной таблицей, значения зон тоже разнесены по столбцам.</p>}
        </div>
        {dashboardMode === "streams" && (
          <section className="employer-compare-controls" aria-label="Выбор потоков для сравнения">
            <p>Выберите от 2 до 4 потоков. Каждый поток будет проверен по собственному порогу публикации.</p>
            <div className="employer-stream-options">
              {(streams ?? []).map((stream) => (
                <label key={stream.id}>
                  <input
                    type="checkbox"
                    checked={selectedStreamIds.includes(stream.id)}
                    disabled={!selectedStreamIds.includes(stream.id) && selectedStreamIds.length >= 4}
                    onChange={(event) => {
                      comparisonRequestId.current += 1;
                      setSelectedStreamIds((current) => event.target.checked
                        ? [...current, stream.id]
                        : current.filter((id) => id !== stream.id));
                      setComparison(null);
                    }}
                  />
                  <span>{stream.name || `Поток ${stream.id}`}</span>
                </label>
              ))}
            </div>
            <button type="button" onClick={() => void handleCompare()} disabled={comparing || !streams || !bundles || selectedStreamIds.length < 2}>
              {comparing ? "Сравниваем…" : "Показать сравнение"}
            </button>
          </section>
        )}
        {dashboardMode === "periods" && (
          <section className="employer-compare-controls" aria-label="Выбор периодов для сравнения">
            <p>Когорта определяется по дате создания сессии участника. Периоды должны быть непересекающимися.</p>
            <div className="employer-period-options">
              <fieldset>
                <legend>Первый период</legend>
                <label>С даты <input type="date" value={periodAFrom} onChange={(event) => { comparisonRequestId.current += 1; setPeriodAFrom(event.target.value); setComparison(null); setComparing(false); }} /></label>
                <label>По дату <input type="date" value={periodATo} onChange={(event) => { comparisonRequestId.current += 1; setPeriodATo(event.target.value); setComparison(null); setComparing(false); }} /></label>
              </fieldset>
              <fieldset>
                <legend>Второй период</legend>
                <label>С даты <input type="date" value={periodBFrom} onChange={(event) => { comparisonRequestId.current += 1; setPeriodBFrom(event.target.value); setComparison(null); setComparing(false); }} /></label>
                <label>По дату <input type="date" value={periodBTo} onChange={(event) => { comparisonRequestId.current += 1; setPeriodBTo(event.target.value); setComparison(null); setComparing(false); }} /></label>
              </fieldset>
            </div>
            <button type="button" onClick={() => void handleCompare()} disabled={comparing || !bundles || !periodAFrom || !periodATo || !periodBFrom || !periodBTo}>
              {comparing ? "Сравниваем…" : "Показать сравнение"}
            </button>
          </section>
        )}
      </header>

      {error && <p className="employer-error">{error}</p>}
      {dashboardMode === "overview" && !overview && !error && <p className="employer-loading">Загрузка…</p>}

      {dashboardMode === "overview" && overview && (
        <>
          <section className="employer-summary">
            <div className="employer-stat">
              <span className="employer-stat__value">{overview.coverage.participants}</span>
              <span className="employer-stat__label">Участников в охвате</span>
            </div>
            <div className="employer-stat">
              <span className="employer-stat__value">{overview.completion.baseline_completed}</span>
              <span className="employer-stat__label">Прошли входной этап</span>
            </div>
            <div className="employer-stat">
              <span className="employer-stat__value">{overview.completion.followup_completed}</span>
              <span className="employer-stat__label">Прошли итоговый этап</span>
            </div>
          </section>

          {overview.iipb && <IIPBOverviewCard data={overview.iipb} />}
          <section className="employer-indicators">
            {overview.indicators.map((indicator) => (
              <article key={indicator.indicator_code} className="employer-card">
                <h2>{indicator.label}</h2>
                <div className="employer-card__stages">
                  <StageColumn title="Входной этап" block={indicator.baseline} />
                  <StageColumn title="Итоговый этап" block={indicator.followup} />
                </div>
                <div className="employer-card__trend">
                  {indicator.trend.is_suppressed ? (
                    <SuppressedNote count={indicator.trend.paired_count} />
                  ) : (
                    <>
                      <span className="employer-trend employer-trend--improved">
                        Улучшение: {indicator.trend.improved}
                      </span>
                      <span className="employer-trend employer-trend--worsened">
                        Ухудшение: {indicator.trend.worsened}
                      </span>
                      <span className="employer-trend employer-trend--stable">
                        {TREND_LABEL.stable}: {indicator.trend.stable}
                      </span>
                    </>
                  )}
                </div>
              </article>
            ))}
          </section>

          <p className="employer-footnote">
            {overview.iipb ? "ИИПБ рассчитывается по методологии v0.1 от 16.11.2026. Личностная тревожность — только фоновый маркер. " : "Результаты показаны по отдельным шкалам. "}
            Индивидуальные ответы и токены участников работодателю не передаются.
          </p>
        </>
      )}
      {comparison && <ComparisonResults comparison={comparison} />}
    </div>
  );
}

function StageColumn({ title, block }: { title: string; block: { participant_count: number; is_suppressed: boolean; mean?: number; zone_distribution?: Record<string, number> } }) {
  if (block.is_suppressed) {
    return (
      <div className="employer-stage">
        <h3>{title}</h3>
        <SuppressedNote count={block.participant_count} />
      </div>
    );
  }
  return (
    <div className="employer-stage">
      <h3>{title}</h3>
      <div className="employer-mean">{block.mean}</div>
      <ul className="employer-distribution">
        {Object.entries(block.zone_distribution ?? {}).map(([zone, count]) => (
          <li key={zone}>
            <span>{zone}</span>
            <span>{count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SuppressedNote({ count }: { count: number }) {
  return (
    <p className="employer-suppressed">
      Группа слишком мала для публикации ({count} участник(ов)) — данные скрыты, чтобы не
      раскрыть результат конкретного человека.
    </p>
  );
}

function ComparisonResults({ comparison }: { comparison: ComparisonResult }) {
  return (
    <section className="employer-comparison-results">
      <h2>{comparison.mode === "streams" ? "Сравнение потоков" : "Сравнение периодов"}</h2>
      <div className="employer-comparison-groups">
        {comparison.groups.map(({ key, label, threshold, overview }) => (
          <article className="employer-comparison-group" key={key}>
            <header>
              <h3>{label}</h3>
              <p>
                Участников: {overview.coverage.participants} · порог публикации: {threshold}
              </p>
              <p>
                Входной этап завершили: {overview.completion.baseline_completed} · итоговый: {overview.completion.followup_completed}
              </p>
            </header>
            {overview.iipb && <IIPBOverviewCard data={overview.iipb} />}
            {overview.indicators.map((indicator) => (
              <section className="employer-comparison-indicator" key={indicator.indicator_code}>
                <h4>{indicator.label}</h4>
                <div className="employer-card__stages">
                  <StageColumn title="Входной этап" block={indicator.baseline} />
                  <StageColumn title="Итоговый этап" block={indicator.followup} />
                </div>
                <div className="employer-card__trend">
                  {indicator.trend.is_suppressed ? (
                    <SuppressedNote count={indicator.trend.paired_count} />
                  ) : (
                    <>
                      <span className="employer-trend employer-trend--improved">Улучшение: {indicator.trend.improved}</span>
                      <span className="employer-trend employer-trend--worsened">Ухудшение: {indicator.trend.worsened}</span>
                      <span className="employer-trend employer-trend--stable">Без изменений: {indicator.trend.stable}</span>
                    </>
                  )}
                </div>
              </section>
            ))}
          </article>
        ))}
      </div>
      <p className="employer-footnote">
        Средние значения и распределения скрыты отдельно для каждого показателя и этапа, если число результатов меньше порога группы.
        У динамики применяется порог к числу участников с парой результатов «вход/итог».
      </p>
    </section>
  );
}
