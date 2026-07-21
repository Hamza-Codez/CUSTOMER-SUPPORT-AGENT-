import { getToken } from "./auth";

// Base URL of the FastAPI backend. Override in .env.local for deployment.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const OFFLINE_HINT = "is the backend running on :8000?";

/** Thrown for 401/403 so callers can react to identity problems specifically. */
export class AuthError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function guard(res) {
  if (res.status === 401) throw new AuthError(401, "Your session has expired — sign in again.");
  if (res.status === 403) throw new AuthError(403, "Your account doesn't have access to this.");
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return res;
}

export async function fetchMe() {
  const res = await fetch(`${API_URL}/me`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  return (await guard(res)).json();
}

export async function sendChat(message, sessionId) {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  return (await guard(res)).json();
}

export async function fetchTickets() {
  const res = await fetch(`${API_URL}/tickets`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  return (await guard(res)).json();
}

/**
 * Stream a reply from POST /chat/stream.
 *
 * Uses fetch rather than EventSource because the endpoint is a POST with a JSON
 * body and an Authorization header, neither of which EventSource can send.
 *
 * Calls `onEvent` with each decoded frame:
 *   { type: "tool",  name }   a tool started running
 *   { type: "token", text }   a text delta
 *   { type: "done",  reply, session_id }
 *   { type: "error", detail } the agent failed mid-stream
 *
 * The agent can fail after the response has begun, so `error` arrives as a
 * frame with HTTP 200 — a caller that only checks res.ok will miss it.
 */
export async function streamChat(message, sessionId, onEvent, signal) {
  let res;
  try {
    res = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error(`Can't reach the agent — ${OFFLINE_HINT}`);
  }

  if (res.status === 401 || res.status === 403) await guard(res);
  if (!res.ok) throw new Error(`Backend error ${res.status} — ${OFFLINE_HINT}`);
  if (!res.body) throw new Error("This browser can't read streaming responses.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line. A chunk can split one in half,
    // so anything after the last separator stays buffered for the next read.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)));
      } catch {
        // A malformed frame shouldn't kill an otherwise good stream.
      }
    }
  }
}
