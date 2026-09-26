import type { SessionState } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = "Не удалось выполнить запрос.";
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // тело ответа не JSON — оставляем сообщение по умолчанию
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function createSession(entryCode: string): Promise<SessionState> {
  return request<SessionState>("/participant/sessions/", {
    method: "POST",
    body: JSON.stringify({ entry_code: entryCode }),
  });
}

export function getSession(token: string): Promise<SessionState> {
  return request<SessionState>(`/participant/sessions/${encodeURIComponent(token)}/`);
}

export function sendConsent(
  token: string,
  payload: { consent_type: "data_processing" | "informed_notice"; text_version: string; accepted: boolean },
): Promise<SessionState> {
  return request<SessionState>(`/participant/sessions/${encodeURIComponent(token)}/consents/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitAnswer(
  token: string,
  payload: { question_id: number; option_id?: number | null; raw_value?: string },
): Promise<SessionState> {
  return request<SessionState>(`/participant/sessions/${encodeURIComponent(token)}/answers/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
