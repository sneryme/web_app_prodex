import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../httpClient";
import {
  clearSession,
  downloadExport,
  getBundles,
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
import type { BundleSummary, OrganizationOverview, OrganizationSummary, StreamSummary } from "./types";

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
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"pdf" | "xlsx" | null>(null);

  function handleError(e: unknown, fallback: string) {
    if (e instanceof ApiError && e.status === 401) {
      onSessionExpired();
      return;
    }
    setError(e instanceof ApiError ? e.message : fallback);
  }

  useEffect(() => {
    getOrganizations()
      .then((orgs) => {
        setOrganizations(orgs);
        if (orgs.length > 0) setOrganizationId(orgs[0].id);
      })
      .catch((e) => handleError(e, "Не удалось загрузить список организаций."));
  }, []);

  useEffect(() => {
    if (organizationId === null) return;
    setStreamId(null);
    setStreams(null);
    getStreams(organizationId)
      .then(setStreams)
      .catch((e) => handleError(e, "Не удалось загрузить список потоков."));
  }, [organizationId]);

  useEffect(() => {
    if (organizationId === null) return;
    setBundles(null);
    setBundleId(null);
    getBundles(organizationId).then((items) => {
      setBundles(items);
      setBundleId(items[0]?.id ?? null);
    }).catch((e) => handleError(e, "Не удалось загрузить комплекты тестов."));
  }, [organizationId]);

  useEffect(() => {
    if (organizationId === null || bundles === null) return;
    getOverview(organizationId, streamId, bundleId)
      .then((data) => {
        setOverview(data);
        setError(null);
      })
      .catch((e) => handleError(e, "Не удалось загрузить агрегаты."));
  }, [organizationId, streamId, bundleId, bundles]);

  async function handleLogout() {
    try {
      await logoutRequest();
    } catch {
      // токен мог уже истечь/быть отозван — всё равно чистим локальную сессию
    }
    onSessionExpired();
  }

  async function handleExport(format: "pdf" | "xlsx") {
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
        <div className="employer-filters">
          <label>
            Организация
            <select
              value={organizationId ?? ""}
              onChange={(e) => setOrganizationId(Number(e.target.value))}
              disabled={!organizations}
            >
              {(organizations ?? []).map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Поток
            <select
              value={streamId ?? "all"}
              onChange={(e) => setStreamId(e.target.value === "all" ? null : Number(e.target.value))}
              disabled={!streams}
            >
              <option value="all">Все потоки</option>
              {(streams ?? []).map((stream) => (
                <option key={stream.id} value={stream.id}>
                  {stream.code}
                  {stream.name ? ` · ${stream.name}` : ""} ({stream.participant_count})
                </option>
              ))}
            </select>
          </label>
          <label>
            Комплект тестов
            <select
              value={bundleId ?? ""}
              onChange={(e) => setBundleId(e.target.value ? Number(e.target.value) : null)}
              disabled={!bundles}
            >
              {(bundles ?? []).map((bundle) => (
                <option key={bundle.id} value={bundle.id}>{bundle.name}</option>
              ))}
            </select>
          </label>
          <div className="employer-export">
            <button type="button" disabled={!overview || exporting !== null} onClick={() => handleExport("xlsx")}>
              {exporting === "xlsx" ? "Готовим…" : "Скачать XLSX"}
            </button>
            <button type="button" disabled={!overview || exporting !== null} onClick={() => handleExport("pdf")}>
              {exporting === "pdf" ? "Готовим…" : "Скачать PDF"}
            </button>
          </div>
        </div>
      </header>

      {error && <p className="employer-error">{error}</p>}
      {!overview && !error && <p className="employer-loading">Загрузка…</p>}

      {overview && (
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
            Показатели не объединяются в общий индекс — EQ-5D, HADS и Спилбергер–Ханин остаются
            отдельными методиками. Индивидуальные ответы и токены участников работодателю не
            передаются.
          </p>
        </>
      )}
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
