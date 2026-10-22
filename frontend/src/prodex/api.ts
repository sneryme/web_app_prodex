import { request } from "../httpClient";
import type { ClientSummary, LicenseWithOrganization, LoginResponse, OperationsOverview } from "./types";

// Отдельные ключи от employer/api.ts (ТЗ FR-11.6: контуры разделены) — чтобы сессия сотрудника
// в дашборде работодателя и в PRODEX Admin не путались в одном браузере.
const TOKEN_KEY = "pez_prodex_token";
const STAFF_KEY = "pez_prodex_staff";

export interface StaffInfo {
  role: string;
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
    JSON.stringify({ role: login.role, role_display: login.role_display, organization: login.organization }),
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

export function getClients(params: { search?: string; licenseStatus?: string } = {}): Promise<ClientSummary[]> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.licenseStatus) query.set("license_status", params.licenseStatus);
  const qs = query.toString();
  return request<ClientSummary[]>(`/prodex/clients/${qs ? `?${qs}` : ""}`, { headers: authHeaders() });
}

export function getLicenses(status?: string): Promise<LicenseWithOrganization[]> {
  const qs = status ? `?status=${status}` : "";
  return request<LicenseWithOrganization[]>(`/prodex/licenses/${qs}`, { headers: authHeaders() });
}

export function getOperations(): Promise<OperationsOverview> {
  return request<OperationsOverview>("/prodex/operations/", { headers: authHeaders() });
}
