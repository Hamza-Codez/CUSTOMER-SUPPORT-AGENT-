/**
 * The single door to the backend.
 *
 * Every call goes through here so the base URL, the auth header and error
 * handling are stated once. A component that fetches on its own is a component
 * that will eventually forget one of them.
 */

import type {
  ChatResponse,
  DecisionResponse,
  EmailPreview,
  EscalationList,
  FeedbackSummary,
  Health,
  Overview,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "fte.token";
const ROLE_KEY = "fte.role";

/** Thrown for any non-2xx, carrying the backend's `detail` when it sent one. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getRole(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ROLE_KEY);
}

export function signIn(token: string, role: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(ROLE_KEY, role);
}

export function signOut() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(ROLE_KEY);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<T> {
  const { method = "GET", body, token = getToken() } = options;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    // A dead backend is the most common failure in development, so it gets a
    // message that says what to do rather than "Failed to fetch".
    throw new ApiError(
      `Can't reach the backend at ${API_BASE}. Is it running? ` +
        `Try: cd backend && uv run uvicorn app.main:app --reload`,
      0,
    );
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      /* body was not JSON; the status line is the best we have */
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

/**
 * The demo tour needs to act as both sides of the conversation in one browser
 * tab — chat as the customer, then approve as the operator — so calls accept an
 * explicit token. These are the public demo tokens against seed data; nothing
 * here is a way around the backend's auth, which still checks every one.
 */
export const DEMO_CUSTOMER_TOKEN = "demo-token";
export const DEMO_OPERATOR_TOKEN = "ops-token";

export const api = {
  health: () => request<Health>("/health", { token: null }),

  chat: (message: string, sessionId: string, token?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: { message, session_id: sessionId },
      ...(token ? { token } : {}),
    }),

  escalations: (
    status?: "pending" | "approved" | "declined",
    token?: string,
  ) =>
    request<EscalationList>(
      `/dashboard/escalations${status ? `?status_filter=${status}` : ""}`,
      token ? { token } : {},
    ),

  decide: (
    id: string,
    decision: "approve" | "decline",
    reason?: string,
    token?: string,
  ) =>
    request<DecisionResponse>(`/escalations/${id}/decision`, {
      method: "POST",
      body: { decision, reason: reason || null },
      ...(token ? { token } : {}),
    }),

  feedback: (token?: string) =>
    request<FeedbackSummary>("/dashboard/feedback", token ? { token } : {}),

  overview: (token?: string) =>
    request<Overview>("/dashboard/overview", token ? { token } : {}),

  emailPreview: (sessionId: string, token?: string) =>
    request<EmailPreview>(
      `/dashboard/emails/${encodeURIComponent(sessionId)}`,
      token ? { token } : {},
    ),
};
