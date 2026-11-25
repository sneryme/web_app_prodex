import { useState } from "react";
import type { ParticipantHomeState } from "../types";
import { TokenBadge } from "./TokenBadge";

interface Props {
  home: ParticipantHomeState;
  onContinue: () => void;
}

export function TokenNoticeScreen({ home, onContinue }: Props) {
  const [saved, setSaved] = useState(false);

  return (
    <section className="card">
      <span className="tag">{"\u0412\u0430\u0436\u043d\u043e"}</span>
      <h2>{"\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u0435 \u043a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430"}</h2>
      <p>Этот код нужен, чтобы вернуться к тестам и открыть свои результаты.</p>
      <TokenBadge token={home.token} />
      <label className="consent-checkbox">
        <input type="checkbox" checked={saved} onChange={(event) => setSaved(event.target.checked)} />
        {"\u042f \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u043b(\u0430) \u043a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430"}
      </label>
      <button type="button" disabled={!saved} onClick={onContinue}>
        {"\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"}
      </button>
    </section>
  );
}
