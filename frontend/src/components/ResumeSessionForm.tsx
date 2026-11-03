import { useState, type FormEvent } from "react";
import { ApiError } from "../api";

interface Props {
  onResume: (token: string) => Promise<void>;
}

export function ResumeSessionForm({ onResume }: Props) {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = token.trim();
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      await onResume(value);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not resume this session. Please try again.");
      setBusy(false);
    }
  }

  return (
    <form className="resume-form" onSubmit={submit}>
      <h3>{"\u0423\u0436\u0435 \u043d\u0430\u0447\u0430\u043b\u0438?"}</h3>
      <p>{"\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c."}</p>
      <label htmlFor="participant-token">{"\u041a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430"}</label>
      <div className="resume-form__controls">
        <input
          id="participant-token"
          autoComplete="off"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !token.trim()}>
          {busy ? "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430\u2026" : "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"}
        </button>
      </div>
      {error && <p className="error-banner" role="alert">{error}</p>}
    </form>
  );
}
