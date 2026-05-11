export type DetectedSummary = {
  frontend: string[];
  backend: string[];
  database: string[];
  styles: string[];
  payments: string[];
  docker: string[];
  notes: string[];
};

export type AnalyzeResponse = {
  job_id: string;
  detected: DetectedSummary;
};

export type StatusResponse = {
  job_id: string;
  state: string;
  step: string;
  progress: number;
  eta_seconds?: number | null;
  error?: string | null;
};

export type AnalyzeStartResponse = {
  job_id: string;
  status: StatusResponse;
};

export type Selection = {
  frontend?: string;
  backend?: string;
  database?: string;
  styles?: string;
};

export type ConvertRequest = {
  job_id: string;
  selection: Selection;
};

export type Report = {
  score: number;
  success_rate: number;
  files_total: number;
  files_converted: number;
  issues: string[];
  warnings: string[];
};

export type ConvertResponse = {
  job_id: string;
  report: Report;
  download_url: string;
};
