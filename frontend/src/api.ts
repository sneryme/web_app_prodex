import { request } from "./httpClient";
import type { ParticipantEntryContext, ParticipantHomeState, ParticipantStream, PersonalReport, SessionState } from "./types";

export { ApiError } from "./httpClient";

export function getAvailableStreams(entryCode: string): Promise<ParticipantStream[]> {
  return request<ParticipantStream[]>("/participant/streams/", {
    method: "POST",
    body: JSON.stringify({ entry_code: entryCode }),
  });
}

export function getEntryContext(entryCode: string): Promise<ParticipantEntryContext> {
  return request<ParticipantEntryContext>("/participant/entry/", {
    method: "POST",
    body: JSON.stringify({ entry_code: entryCode }),
  });
}

export function createSession(entryCode: string, streamId: number | null): Promise<ParticipantHomeState> {
  return request<ParticipantHomeState>("/participant/sessions/", {
    method: "POST",
    body: JSON.stringify({ entry_code: entryCode, stream_id: streamId }),
  });
}

export function getSession(token: string): Promise<ParticipantHomeState> {
  return request<ParticipantHomeState>(`/participant/sessions/${encodeURIComponent(token)}/`);
}

export function selectBundle(token: string, bundleId: number): Promise<SessionState> {
  return request<SessionState>(`/participant/sessions/${encodeURIComponent(token)}/bundles/`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId }),
  });
}

export function sendConsent(
  token: string,
  payload: { consent_type: "data_processing" | "informed_notice"; text_version: string; accepted: boolean; bundle_id: number },
): Promise<SessionState> {
  return request<SessionState>(`/participant/sessions/${encodeURIComponent(token)}/consents/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitAnswer(
  token: string,
  payload: { bundle_id: number; stage: NonNullable<SessionState["stage"]>; question_id: number; option_id?: number | null; raw_value?: string },
): Promise<SessionState> {
  return request<SessionState>(`/participant/sessions/${encodeURIComponent(token)}/answers/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getReport(token: string, bundleId: number): Promise<PersonalReport> {
  return request<PersonalReport>(`/participant/reports/${encodeURIComponent(token)}/?bundle_id=${bundleId}`);
}
