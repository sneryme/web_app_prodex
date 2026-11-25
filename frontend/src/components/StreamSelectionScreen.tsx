import { useState, type FormEvent } from "react";
import { ApiError } from "../api";
import type { ParticipantStream } from "../types";

interface Props {
  streams: ParticipantStream[];
  onSelect: (streamId: number | null) => void;
  onResume: (token: string) => Promise<void>;
}

export function StreamSelectionScreen({ streams, onSelect, onResume }: Props) {
  const [selectedStreamId, setSelectedStreamId] = useState<number | "">("");
  const [participantCode, setParticipantCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const code = participantCode.trim();
    if (code) {
      setBusy(true);
      try {
        await onResume(code);
      } catch (cause) {
        setError(cause instanceof ApiError ? cause.message : "Could not resume this session. Please try again.");
        setBusy(false);
      }
      return;
    }

    onSelect(selectedStreamId === "" ? null : selectedStreamId);
  }

  return (
    <section className="card">
      <span className="tag">{"\u0423\u0447\u0430\u0441\u0442\u0438\u0435 \u0432 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435"}</span>
      <h2>{"\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u043e\u0442\u043e\u043a"}</h2>
      <form className="stream-entry-form" onSubmit={submit}>
        {streams.length > 0 && (
          <>
            <p>{"\u0423\u043a\u0430\u0436\u0438\u0442\u0435 \u043e\u0442\u0434\u0435\u043b, \u043a \u043a\u043e\u0442\u043e\u0440\u043e\u043c\u0443 \u0432\u044b \u043e\u0442\u043d\u043e\u0441\u0438\u0442\u0435\u0441\u044c."}</p>
            <div className="stream-select-wrap">
              <label className="stream-select-label" htmlFor="participant-stream">
                {"\u041e\u0442\u0434\u0435\u043b"}
              </label>
              <select
                id="participant-stream"
                className="stream-select"
                value={selectedStreamId}
                onChange={(event) => setSelectedStreamId(event.target.value ? Number(event.target.value) : "")}
                disabled={busy}
              >
                <option value="" disabled>
                  {"\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0432\u043e\u0439 \u043e\u0442\u0434\u0435\u043b"}
                </option>
                {streams.map((stream) => (
                  <option key={stream.id} value={stream.id}>
                    {stream.name ? `${stream.name} (${stream.code})` : stream.code}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
        <div className="resume-form">
          <h3>{"\u0423\u0436\u0435 \u043d\u0430\u0447\u0430\u043b\u0438?"}</h3>
          <p>{"\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u043d\u0430\u0447\u0430\u0442\u044b\u0439 \u0442\u0435\u0441\u0442. \u0415\u0441\u043b\u0438 \u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u043f\u043e\u043b\u0435 \u043f\u0443\u0441\u0442\u044b\u043c, \u0431\u0443\u0434\u0435\u0442 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0439 \u043e\u0442\u0434\u0435\u043b."}</p>
          <label htmlFor="participant-token">{"\u041a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430"}</label>
          <input
            id="participant-token"
            autoComplete="off"
            value={participantCode}
            onChange={(event) => setParticipantCode(event.target.value)}
            disabled={busy}
          />
        </div>
        {error && <p className="error-banner" role="alert">{error}</p>}
        {streams.length === 0 && !participantCode.trim() && (
          <p>{"\u0414\u043b\u044f \u044d\u0442\u043e\u0439 \u043e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0446\u0438\u0438 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u043f\u043e\u0442\u043e\u043a\u043e\u0432. \u041c\u043e\u0436\u043d\u043e \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u0431\u0435\u0437 \u0432\u044b\u0431\u043e\u0440\u0430 \u043f\u043e\u0442\u043e\u043a\u0430."}</p>
        )}
        <button type="submit" disabled={busy || (!participantCode.trim() && streams.length > 0 && selectedStreamId === "")}>
          {busy ? "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430\u2026" : "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"}
        </button>
      </form>
    </section>
  );
}
