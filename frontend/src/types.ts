export type ConsentStatus = "required" | "granted" | "declined";
export type Stage = "baseline" | "followup" | null;
export type StageStatus = "not_started" | "in_progress" | "completed" | null;

export interface AnswerOptionDTO {
  id: number;
  value: number;
  label: string;
}

export interface QuestionDTO {
  id: number;
  code: string;
  text: string;
  indicator_code: string;
  questionnaire_code: string;
  options: AnswerOptionDTO[];
  answer: { option_id: number | null; raw_value: string } | null;
}

export interface SessionState {
  token: string;
  is_test?: boolean;
  bundle_id: number | null;
  bundle_name: string;
  methodology?: string;
  followup_locked?: boolean;
  followup_available_at?: string | null;
  baseline_result?: IIPBMeasurement | null;
  routing_contacts?: RoutingContacts;
  consent_status: ConsentStatus;
  stage: Stage;
  stage_status: StageStatus;
  questions: QuestionDTO[];
  questionnaires: { code: string; name: string; question_count: number; answered_count: number }[];
  progress: { answered: number; total: number };
}

export interface BundleChoice {
  id: number;
  code: string;
  name: string;
  methodology?: string;
  status: "not_started" | "in_progress" | "completed";
  baseline: { answered: number; total: number };
  followup: { answered: number; total: number };
  questionnaires: {
    code: string;
    name: string;
    question_count: number;
    baseline_answered: number;
    followup_answered: number;
  }[];
}

export interface ParticipantHomeState {
  token: string;
  is_test?: boolean;
  organization_id: number;
  consent_status: ConsentStatus;
  bundles: BundleChoice[];
}

export interface ParticipantStream {
  id: number;
  code: string;
  name: string;
}

export interface ParticipantEntryContext {
  organization_id: number;
  streams: ParticipantStream[];
}

export type Trend = "improved" | "worsened" | "stable";

export interface ReportCard {
  indicator_code: string;
  label: string;
  before: { raw_score: number; zone: string };
  after: { raw_score: number; zone: string };
  change: number;
  trend: Trend;
}

export interface Eq5dProfileItem {
  indicator_code: string;
  label: string;
  before: number;
  after: number;
}

export interface PersonalReport {
  token: string;
  is_test?: boolean;
  summary: string;
  improved_count: number;
  total_count: number;
  cards: ReportCard[];
  eq5d_profile: Eq5dProfileItem[];
  methodology?: string;
  status?: "baseline_only" | "completed";
  routing_contacts?: RoutingContacts;
  iipb?: { baseline: IIPBMeasurement; followup: IIPBMeasurement | null; dynamics: IIPBDynamics | null };
}

export interface RoutingContacts { specialist: string; physician: string }
export interface IIPBFlag { code: string; label: string; action: string }
export interface IIPBMeasurement {
  version: string;
  version_date: string;
  measured_at: string;
  notice: string;
  index: number;
  level: string;
  level_label: string;
  conclusion: string;
  action: string;
  red_flags: IIPBFlag[];
  yellow_flags: IIPBFlag[];
  trait_marker: { raw_score: number; label: string };
  inputs: Record<string, number>;
  lss: number;
  domains: Record<string, number>;
  subindices: Record<string, number>;
}
export interface IIPBDynamics {
  delta_pp: number;
  delta_percent: number | null;
  level_change: string;
  trend: Trend;
  summary: string;
  notice: string;
  actions: string[];
}
