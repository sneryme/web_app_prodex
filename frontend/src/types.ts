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
  bundle_id: number | null;
  bundle_name: string;
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
  consent_status: ConsentStatus;
  bundles: BundleChoice[];
}

export interface ParticipantStream {
  id: number;
  code: string;
  name: string;
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
  summary: string;
  improved_count: number;
  total_count: number;
  cards: ReportCard[];
  eq5d_profile: Eq5dProfileItem[];
}
