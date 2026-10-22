// ТЗ FR-11.5: здесь нет и не должно быть психологических показателей участников — только
// организационные и технические данные (лицензии, потоки, участники количественно).

export interface LoginResponse {
  token: string;
  role: string;
  role_display: string;
  organization: { id: number; name: string } | null;
}

export interface LicenseSummary {
  id: number;
  starts_at: string;
  ends_at: string;
  status: string;
  status_display: string;
  is_expired: boolean;
}

export interface ClientSummary {
  id: number;
  name: string;
  legal_name: string;
  license: LicenseSummary | null;
  streams_count: number;
  participants_count: number;
}

export interface LicenseWithOrganization extends LicenseSummary {
  organization: { id: number; name: string };
}

export interface OperationsOverview {
  organizations_count: number;
  licenses: Record<string, number>;
  streams: Record<string, number>;
  participants: Record<string, number>;
  completion: { baseline_completed: number; followup_completed: number };
  activity: { new_participants_last_30d: number };
  errors: { unscored_answer_groups: number };
}
