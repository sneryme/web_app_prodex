import { ApiError, request } from "../httpClient";
import type { LoginResponse, OrganizationOverview, OrganizationSummary, StreamSummary } from "./types";

const TOKEN_KEY = "pez_employer_token";
const STAFF_KEY = "pez_employer_staff";
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export interface StaffInfo {
  role_display: string;
  organization: { id: number; name: string } | null;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStaffInfo(): StaffInfo | null {
  const raw = localStorage.getItem(STAFF_KEY);
  return raw ? (JSON.parse(raw) as StaffInfo) : null;
}

export function setSession(login: LoginResponse): void {
  localStorage.setItem(TOKEN_KEY, login.token);
  localStorage.setItem(
    STAFF_KEY,
    JSON.stringify({ role_display: login.role_display, organization: login.organization }),
  );
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(STAFF_KEY);
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Token ${token}` } : {};
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/identity/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout(): Promise<void> {
  return request<void>("/identity/logout/", { method: "POST", headers: authHeaders() });
}

export function getOrganizations(): Promise<OrganizationSummary[]> {
  return request<OrganizationSummary[]>("/employer/organizations/", { headers: authHeaders() });
}

export function getStreams(organizationId: number): Promise<StreamSummary[]> {
  return request<StreamSummary[]>(`/employer/organizations/${organizationId}/streams/`, { headers: authHeaders() });
}

export function getOverview(organizationId: number, streamId: number | null): Promise<OrganizationOverview> {
  const query = streamId !== null ? `?stream=${streamId}` : "";
  return request<OrganizationOverview>(`/employer/organizations/${organizationId}/overview/${query}`, {
    headers: authHeaders(),
  });
}

// Бинарный ответ (PDF/XLSX) — не JSON, поэтому не через общий request(), а напрямую через fetch.
export async function downloadExport(
  organizationId: number,
  streamId: number | null,
  format: "pdf" | "xlsx",
): Promise<void> {
  // "kind", не "format": "format" у DRF зарезервирован под собственное content negotiation.
  const params = new URLSearchParams({ kind: format });
  if (streamId !== null) params.set("stream", String(streamId));
  const response = await fetch(`${API_URL}/employer/organizations/${organizationId}/export/?${params}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new ApiError(response.status, "Не удалось сформировать экспорт.");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match ? match[1] : `dashboard.${format}`;

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
