import type { LoginResponse, ChatResponse } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = typeof err.detail === "string"
      ? err.detail
      : JSON.stringify(err.detail);
    throw new Error(`${res.status}: ${detail || res.statusText}`);
  }
  return res.json();
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function sendChat(question: string, token: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question }),
  });
}

export async function healthCheck(): Promise<{ status: string }> {
  return request("/health", { method: "GET" });
}
