import type {
  AnalyzeResponse,
  AnalyzeStartResponse,
  ConvertRequest,
  ConvertResponse,
  StatusResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Request failed");
  }
  return (await response.json()) as T;
};

export const getApiBase = () => API_BASE;

export const startAnalyze = async (params: {
  file?: File | null;
  repoUrl?: string;
}): Promise<AnalyzeStartResponse> => {
  const formData = new FormData();
  if (params.file) {
    formData.append("file", params.file);
  }
  if (params.repoUrl) {
    formData.append("repo_url", params.repoUrl);
  }

  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<AnalyzeStartResponse>(response);
};

export const getAnalyzeStatus = async (jobId: string): Promise<StatusResponse> => {
  const response = await fetch(`${API_BASE}/status/${jobId}`);
  return handleResponse<StatusResponse>(response);
};

export const getAnalyzeResult = async (jobId: string): Promise<AnalyzeResponse> => {
  const response = await fetch(`${API_BASE}/analysis/${jobId}`);
  return handleResponse<AnalyzeResponse>(response);
};

export const convertProject = async (payload: ConvertRequest): Promise<ConvertResponse> => {
  const response = await fetch(`${API_BASE}/convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return handleResponse<ConvertResponse>(response);
};
