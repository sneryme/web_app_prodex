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
