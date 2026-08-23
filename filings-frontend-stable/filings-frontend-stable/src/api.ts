// Thin, typed wrapper around the backend API.
// The base URL is configurable so the same build works locally and deployed.

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

// ---- Types mirroring the backend schemas ----
export interface UserOut {
  id: number;
  email: string;
  created_at: string;
}

export interface DocumentOut {
  id: number;
  filename: string;
  created_at: string;
}

export interface AnalysisOut {
  id: number;
  document_id: number;
  question: string;
  answer: string;
  created_at: string;
}

// ---- Token storage ----
// Kept in memory + localStorage so a refresh doesn't log you out.
const TOKEN_KEY = "filings_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---- Core request helper ----
class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail);
    } catch {
      // response wasn't JSON; keep the default message
    }
    throw new ApiError(resp.status, detail);
  }

  // 204 or empty bodies
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

// ---- Auth ----
export async function register(email: string, password: string): Promise<UserOut> {
  return request<UserOut>(
    "/auth/register",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    false,
  );
}

export async function login(email: string, password: string): Promise<string> {
  // The backend's login uses form-encoded data (OAuth2PasswordRequestForm).
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);

  const data = await request<{ access_token: string }>(
    "/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    },
    false,
  );
  setToken(data.access_token);
  return data.access_token;
}

// ---- Documents ----
export async function listDocuments(): Promise<DocumentOut[]> {
  return request<DocumentOut[]>("/documents");
}

export async function uploadDocument(file: File): Promise<DocumentOut> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentOut>("/documents", {
    method: "POST",
    body: form,
  });
}

// ---- Analyses ----
export async function listAnalyses(documentId: number): Promise<AnalysisOut[]> {
  return request<AnalysisOut[]>(`/documents/${documentId}/analyses`);
}

export async function askQuestion(
  documentId: number,
  question: string,
): Promise<AnalysisOut> {
  return request<AnalysisOut>(`/documents/${documentId}/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export { ApiError };
