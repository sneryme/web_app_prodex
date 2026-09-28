export type ConsentStatus = "required" | "granted" | "declined";
export type Stage = "baseline" | "followup" | null;

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
  options: AnswerOptionDTO[];
  answer: { option_id: number | null; raw_value: string } | null;
}

export interface SessionState {
  token: string;
  consent_status: ConsentStatus;
  stage: Stage;
  questions: QuestionDTO[];
  progress: { answered: number; total: number };
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
