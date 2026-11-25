import { useState } from "react";
import { sendConsent } from "../api";
import type { SessionState } from "../types";

// Черновая версия текста согласия — заменить после утверждения юристом (см. project/DATA_PROTECTION.md).
const CONSENT_TEXT_VERSION = "v1";

interface Props {
  session: SessionState;
  onResult: (session: SessionState) => void;
}

/** ТЗ FR-03: отдельный экран согласия/информирования; чекбокс по умолчанию не отмечен. */
export function ConsentScreen({ session, onResult }: Props) {
  const [checked, setChecked] = useState(false);
  const [informed, setInformed] = useState(false);
  const [adult, setAdult] = useState(false);
  const isIIPB = session.methodology === "iipb-0.1";
  const textVersion = isIIPB ? session.methodology! : CONSENT_TEXT_VERSION;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await sendConsent(session.token, {
        consent_type: "informed_notice",
        text_version: textVersion,
        accepted: true,
        bundle_id: session.bundle_id ?? 0,
      });
      const updated = await sendConsent(session.token, {
        consent_type: "data_processing",
        text_version: textVersion,
        accepted: true,
        bundle_id: session.bundle_id ?? 0,
      });
      onResult(updated);
    } catch {
      setBusy(false);
      setError("Не удалось сохранить согласие. Проверьте соединение и попробуйте ещё раз.");
    }
  }

  async function decline() {
    setBusy(true);
    setError(null);
    try {
      const updated = await sendConsent(session.token, {
        consent_type: "data_processing",
        text_version: textVersion,
        accepted: false,
        bundle_id: session.bundle_id ?? 0,
      });
      onResult(updated);
    } catch {
      setBusy(false);
      setError("Не удалось сохранить отказ. Проверьте соединение и попробуйте ещё раз.");
    }
  }

  return (
    <section className="card">
      <span className="tag">Шаг 2 из 3 · Согласие</span>
      <h2>Прежде чем начать</h2>
      <p>
        Тестирование включает опросники EQ-5D, Спилбергера–Ханина и HADS. Результат видите только вы;
        работодатель получает обезличенную групповую статистику без вашего личного результата.
      </p>
      {isIIPB && <>
        <p>ИИПБ v0.1 объединяет результаты HADS, Спилбергера–Ханина и EQ-5D-5L. Это предварительная, не валидированная методика. Результат не является диагнозом и не применяется для кадровых решений. При выраженных трудностях будет предложено обратиться к специалисту.</p>
        <label className="consent-checkbox"><input type="checkbox" checked={adult} onChange={event => setAdult(event.target.checked)} />Мне исполнилось 18 лет; я могу самостоятельно заполнить опросники.</label>
        <label className="consent-checkbox"><input type="checkbox" checked={informed} onChange={event => setInformed(event.target.checked)} />Я ознакомлен(а) с целью, ограничениями ИИПБ и добровольным характером участия.</label>
      </>}
      <label className="consent-checkbox">
        <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
        Я согласен(на) на обработку {isIIPB ? "сведений о состоянии здоровья и ответов на опросники" : "персональных данных"} в рамках тестирования
      </label>
      {error && <p className="error-banner">{error}</p>}
      <div className="actions">
        <button type="button" disabled={!checked || (isIIPB && (!adult || !informed)) || busy} onClick={accept}>
          Продолжить
        </button>
        <button type="button" className="ghost" disabled={busy} onClick={decline}>
          Отказаться от участия
        </button>
      </div>
    </section>
  );
}
