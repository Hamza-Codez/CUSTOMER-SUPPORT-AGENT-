"use client";

const KEY = "digital-fte:session-id";

function newId() {
  return "web-" + Math.random().toString(36).slice(2, 8);
}

/**
 * The session id survives a reload, so a refresh resumes the conversation
 * instead of silently starting a new one. Server-side memory is keyed by this.
 */
export function loadSessionId() {
  if (typeof window === "undefined") return null;   // SSR pass has no storage
  try {
    const existing = window.localStorage.getItem(KEY);
    if (existing) return existing;
    const created = newId();
    window.localStorage.setItem(KEY, created);
    return created;
  } catch {
    return newId();   // private mode / storage disabled — degrade, don't crash
  }
}

export function resetSessionId() {
  const created = newId();
  try {
    window.localStorage.setItem(KEY, created);
  } catch {
    /* nothing to persist to; the in-memory id still works for this tab */
  }
  return created;
}
