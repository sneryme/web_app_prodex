import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../httpClient";
import {
  clearSession,
  getClients,
  getLicenses,
  getOperations,
  getStaffInfo,
  getToken,
  login as loginRequest,
  logout as logoutRequest,
  setSession,
  type StaffInfo,
} from "./api";
import type { ClientSummary, LicenseWithOrganization, OperationsOverview } from "./types";

const LICENSE_STATUS_LABEL: Record<string, string> = {
  active: "Активна",
  expired: "Истекла",
  suspended: "Приостановлена",
};

/**
 * Операционный контур администратора PRODEX (ТЗ FR-11) — отдельный от дашборда работодателя
 * (ТЗ FR-11.6, PROJECT_RULES №9): свой маршрут `/prodex`, свой React-компонент, своя сессия
 * (см. api.ts), не делит ничего из frontend/src/employer/. Психологических результатов
 * участников здесь нет и не должно быть (ТЗ FR-11.5) — только клиенты, лицензии и технические
 * метрики. Вход — тот же `identity.StaffProfile`/DRF TokenAuthentication, что и у работодателя,
 * но доступ к данным проверяется ролью: только администратор PRODEX (apps/identity/permissions.py
 * ::IsProdexAdmin), администратор организации получает 403.
 */
export function ProdexApp() {
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

  if (staff?.role !== "prodex_admin") {
    return <AccessDenied onLogout={handleSessionExpired} />;
  }

  return <Dashboard onSessionExpired={handleSessionExpired} />;
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
      onLoggedIn({ role: response.role, role_display: response.role_display, organization: response.organization });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не удалось войти.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="prodex-shell prodex-shell--login">
      <form className="prodex-login" onSubmit={handleSubmit}>
        <span className="prodex-eyebrow">PRODEX / DIGITAL · Администрирование</span>
        <h1>Вход администратора PRODEX</h1>
        <label>
          Логин
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </label>
        <label>
          Пароль
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="prodex-error">{error}</p>}
        <button type="submit" disabled={pending}>
          {pending ? "Входим…" : "Войти"}
        </button>
      </form>
    </div>
  );
}

function AccessDenied({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="prodex-shell prodex-shell--login">
      <div className="prodex-login">
        <span className="prodex-eyebrow">PRODEX / DIGITAL · Администрирование</span>
        <h1>Доступ запрещён</h1>
        <p className="prodex-error">
          Этот раздел доступен только администратору PRODEX. Администратору организации — дашборд
          работодателя по адресу /employer.
        </p>
        <button type="button" onClick={onLogout}>
          Выйти
        </button>
      </div>
    </div>
  );
}

function Dashboard({ onSessionExpired }: { onSessionExpired: () => void }) {
  const [clients, setClients] = useState<ClientSummary[] | null>(null);
  const [licenses, setLicenses] = useState<LicenseWithOrganization[] | null>(null);
  const [operations, setOperations] = useState<OperationsOverview | null>(null);
  const [search, setSearch] = useState("");
  const [licenseStatus, setLicenseStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleError(e: unknown, fallback: string) {
    if (e instanceof ApiError && e.status === 401) {
      onSessionExpired();
      return;
    }
    setError(e instanceof ApiError ? e.message : fallback);
  }

  useEffect(() => {
    getOperations()
      .then(setOperations)
      .catch((e) => handleError(e, "Не удалось загрузить операционные метрики."));
    getLicenses()
      .then(setLicenses)
      .catch((e) => handleError(e, "Не удалось загрузить лицензии."));
  }, []);

  useEffect(() => {
    getClients({ search, licenseStatus: licenseStatus || undefined })
      .then((data) => {
        setClients(data);
        setError(null);
      })
      .catch((e) => handleError(e, "Не удалось загрузить список клиентов."));
  }, [search, licenseStatus]);

  async function handleLogout() {
    try {
      await logoutRequest();
    } catch {
      // токен мог уже истечь/быть отозван — всё равно чистим локальную сессию
    }
    onSessionExpired();
  }

  return (
    <div className="prodex-shell">
      <header className="prodex-header">
        <div className="prodex-header__top">
          <span className="prodex-eyebrow">PRODEX / DIGITAL · Администрирование</span>
          <button type="button" className="prodex-session__logout" onClick={handleLogout}>
            Выйти
          </button>
        </div>
        <h1>Операционный контур PRODEX</h1>
      </header>

      {error && <p className="prodex-error">{error}</p>}

      <section className="prodex-section">
        <h2>Технические и операционные показатели</h2>
        {!operations ? (
          <p className="prodex-loading">Загрузка…</p>
        ) : (
          <div className="prodex-stats">
            <Stat label="Организаций" value={operations.organizations_count} />
            <Stat label="Участников всего" value={operations.participants.total} />
            <Stat label="Прошли входной этап" value={operations.completion.baseline_completed} />
            <Stat label="Прошли итоговый этап" value={operations.completion.followup_completed} />
            <Stat label="Новых участников за 30 дней" value={operations.activity.new_participants_last_30d} />
            <Stat
              label="Ошибки подсчёта"
              value={operations.errors.unscored_answer_groups}
              warn={operations.errors.unscored_answer_groups > 0}
            />
          </div>
        )}
      </section>

      <section className="prodex-section">
        <h2>Клиенты</h2>
        <div className="prodex-filters">
          <label>
            Поиск
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Название организации" />
          </label>
          <label>
            Статус лицензии
            <select value={licenseStatus} onChange={(e) => setLicenseStatus(e.target.value)}>
              <option value="">Все</option>
              <option value="active">Активна</option>
              <option value="expired">Истекла</option>
              <option value="suspended">Приостановлена</option>
            </select>
          </label>
        </div>

        {!clients ? (
          <p className="prodex-loading">Загрузка…</p>
        ) : (
          <table className="prodex-table">
            <thead>
              <tr>
                <th>Организация</th>
                <th>Лицензия</th>
                <th>Потоков</th>
                <th>Участников</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr key={client.id}>
                  <td>{client.name}</td>
                  <td>
                    {client.license ? (
                      <span
                        className={
                          client.license.is_expired ? "prodex-badge prodex-badge--expired" : "prodex-badge"
                        }
                      >
                        {LICENSE_STATUS_LABEL[client.license.status] ?? client.license.status}
                        {client.license.is_expired ? " · срок истёк" : ""} · до {client.license.ends_at}
                      </span>
                    ) : (
                      <span className="prodex-badge prodex-badge--none">Лицензии нет</span>
                    )}
                  </td>
                  <td>{client.streams_count}</td>
                  <td>{client.participants_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="prodex-section">
        <h2>Лицензии</h2>
        {!licenses ? (
          <p className="prodex-loading">Загрузка…</p>
        ) : (
          <table className="prodex-table">
            <thead>
              <tr>
                <th>Организация</th>
                <th>Период</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {licenses.map((license) => (
                <tr key={license.id}>
                  <td>{license.organization.name}</td>
                  <td>
                    {license.starts_at} – {license.ends_at}
                  </td>
                  <td>
                    {LICENSE_STATUS_LABEL[license.status] ?? license.status}
                    {license.is_expired ? " · срок истёк" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p className="prodex-footnote">
        Индивидуальные психологические результаты участников здесь не отображаются — только
        организационные и технические данные (ТЗ FR-11.5).
      </p>
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className={warn ? "prodex-stat prodex-stat--warn" : "prodex-stat"}>
      <span className="prodex-stat__value">{value}</span>
      <span className="prodex-stat__label">{label}</span>
    </div>
  );
}
