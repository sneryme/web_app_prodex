import { request } from "./httpClient";
import type { PersonalReport, SessionState } from "./types";

export { ApiError } from "./httpClient";

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

export function getReport(token: string): Promise<PersonalReport> {
  return request<PersonalReport>(`/participant/reports/${encodeURIComponent(token)}/`);
}
