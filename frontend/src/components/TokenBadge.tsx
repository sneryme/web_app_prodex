import { useState } from "react";

/** ТЗ FR-01.2: участник может увидеть и сохранить свой токен. */
export function TokenBadge({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Буфер обмена недоступен — код всё равно виден на экране, участник может переписать его вручную.
    }
  }

  return (
    <div className="token-box">
      <span>Ваш код участника — сохраните его, он понадобится для повторного входа:</span>
      <code>{token}</code>
      <button type="button" className="ghost" onClick={copy}>
        {copied ? "Скопировано" : "Скопировать"}
      </button>
    </div>
  );
}
