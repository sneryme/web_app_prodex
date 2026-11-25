// ТЗ FR-09.5: здесь нет и не должно быть ничего на уровне отдельного участника — ни токенов,
// ни ответов. Только счётчики и средние по группе.

export interface LoginResponse {
  token: string;
  role: string;
  role_display: string;
  organization: { id: number; name: string } | null;
}

export interface OrganizationSummary {
  id: number;
  name: string;
}

export interface StreamSummary {
  id: number;
  code: string;
  name: string;
  status: string;
  participant_count: number;
}

export interface BundleSummary {
  id: number;
  code: string;
  name: string;
}

export interface StageBlock {
  participant_count: number;
  is_suppressed: boolean;
  mean?: number;
  zone_distribution?: Record<string, number>;
  median?: number;
  red_flag_count?: number;
  yellow_flag_count?: number;
  flag_distribution?: Record<string, number>;
  trait_distribution?: Record<string, number>;
}

export interface TrendBlock {
  paired_count: number;
  is_suppressed: boolean;
  improved?: number;
  worsened?: number;
  stable?: number;
  mean_delta?: number;
  median_delta?: number;
}

export interface IndicatorOverview {
  indicator_code: string;
  label: string;
  baseline: StageBlock;
  followup: StageBlock;
  trend: TrendBlock;
}

export interface OrganizationOverview {
  organization: OrganizationSummary;
  bundle: BundleSummary | null;
  stream: { id: number; code: string; name: string } | null;
  coverage: { participants: number };
  completion: { baseline_completed: number; followup_completed: number };
  indicators: IndicatorOverview[];
  iipb?: IIPBOverview | null;
}

export interface IIPBOverview {
  version: string;
  version_date: string;
  threshold: number;
  notice: string;
  dynamics_notice: string;
  baseline: StageBlock;
  followup: StageBlock;
  trend: TrendBlock;
}

export interface ComparisonGroup {
  key: string;
  label: string;
  threshold: number;
  date_from?: string;
  date_to?: string;
  overview: OrganizationOverview;
}

export interface ComparisonResult {
  mode: "streams" | "periods";
  groups: ComparisonGroup[];
}
