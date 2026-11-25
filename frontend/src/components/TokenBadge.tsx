import { useState } from "react";

export function TokenBadge({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // The token remains visible so it can still be copied manually.
    }
  }

  return (
    <div className="token-box">
      <span>{"\u0412\u0430\u0448 \u043a\u043e\u0434 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0430. \u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u0435 \u0435\u0433\u043e: \u043e\u043d \u043f\u043e\u043d\u0430\u0434\u043e\u0431\u0438\u0442\u0441\u044f \u0434\u043b\u044f \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e\u0433\u043e \u0432\u0445\u043e\u0434\u0430."}</span>
      <code>{token}</code>
      <button type="button" className="ghost" onClick={copy}>
        {copied ? "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u043e" : "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c"}
      </button>
    </div>
  );
}
