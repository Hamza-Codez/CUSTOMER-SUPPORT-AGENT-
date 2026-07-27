/**
 * The single door to the backend.
 *
 * Every call goes through here so the base URL, the auth header and error
 * handling are stated once. A component that fetches on its own is a component
 * that will eventually forget one of them.
 */

import type {
  Account,
  Analytics,
  AuthResponse,
  ChatResponse,
  DecisionResponse,
  EmailPreview,
  EscalationList,
  IntegrationAccepted,
  IntegrationRequestBody,
  FeedbackSummary,
  Health,
  Overview,
  SiteKey,
  SiteKeyList,
  SiteScanResult,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "fte.token";
const ROLE_KEY = "fte.role";
const ACCOUNT_KEY = "fte.account";

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

export function getAccount(): Account | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ACCOUNT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Account;
  } catch {
    return null;
  }
}

export function signIn(token: string, role: string, account?: Account) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(ROLE_KEY, role);
  if (account) window.localStorage.setItem(ACCOUNT_KEY, JSON.stringify(account));
}

export function signOut() {
  for (const key of [TOKEN_KEY, ROLE_KEY, ACCOUNT_KEY]) {
    window.localStorage.removeItem(key);
  }
}

/** How long any single call may hang before we give up on it.
 *
 * A request with no deadline is why the chat could sit on "Composing a reply…"
 * for ever: fetch does not time out on its own, so a cold backend or a model
 * provider retrying a rate limit left the promise unsettled and the UI with
 * nothing to say. A turn that genuinely takes longer than this is one the
 * customer should be told about rather than left watching. */
const TIMEOUT_MS = 45_000;

export class TimeoutError extends ApiError {
  constructor() {
    super(
      "The agent didn't reply within 45 seconds. It may be starting up, or the " +
        "model provider may be rate-limiting us — the free tier is 20 requests a " +
        "day. Try again, and check the backend logs if it keeps happening.",
      408,
    );
    this.name = "TimeoutError";
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<T> {
  const { method = "GET", body, token = getToken() } = options;

  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), TIMEOUT_MS);

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
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new TimeoutError();
    }
    // A dead backend is the most common failure in development, so it gets a
    // message that says what to do rather than "Failed to fetch".
    throw new ApiError(
      `Can't reach the backend at ${API_BASE}. Is it running? ` +
        `Try: cd backend && uv run uvicorn app.main:app --reload`,
      0,
    );
  } finally {
    clearTimeout(deadline);
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

  // 204 has no body by definition, and calling .json() on one throws — which
  // would turn a successful delete into an error.
  if (response.status === 204) return undefined as T;

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
  signup: (body: {
    business_name: string;
    name: string;
    email: string;
    password: string;
  }) => request<AuthResponse>("/auth/signup", { method: "POST", body, token: null }),

  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body, token: null }),

  me: (token?: string) => request<Account>("/auth/me", token ? { token } : {}),

  onboardingContext: (
    policies: { topic: string; body: string }[],
    token?: string,
  ) =>
    request<{ passages: number; source_refs: string[]; message: string }>(
      "/onboarding/context",
      { method: "POST", body: { policies }, ...(token ? { token } : {}) },
    ),

  scanSite: (url: string, token?: string) =>
    request<SiteScanResult>("/onboarding/scan", {
      method: "POST",
      body: { url },
      ...(token ? { token } : {}),
    }),

  siteKeys: (token?: string) =>
    request<SiteKeyList>("/site-keys", token ? { token } : {}),

  createSiteKey: (
    body: { label?: string; allowed_origins?: string[]; preview?: boolean },
    token?: string,
  ) =>
    request<SiteKey>("/site-keys", {
      method: "POST",
      body,
      ...(token ? { token } : {}),
    }),

  revokeSiteKey: (key: string, token?: string) =>
    request<void>(`/site-keys/${encodeURIComponent(key)}`, {
      method: "DELETE",
      ...(token ? { token } : {}),
    }),

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

  analytics: (token?: string) =>
    request<Analytics>("/dashboard/analytics", token ? { token } : {}),

  requestIntegration: (body: IntegrationRequestBody, token?: string) =>
    request<IntegrationAccepted>("/integrations/request", {
      method: "POST",
      body,
      ...(token ? { token } : {}),
    }),

  emailPreview: (sessionId: string, token?: string) =>
    request<EmailPreview>(
      `/dashboard/emails/${encodeURIComponent(sessionId)}`,
      token ? { token } : {},
    ),
};
