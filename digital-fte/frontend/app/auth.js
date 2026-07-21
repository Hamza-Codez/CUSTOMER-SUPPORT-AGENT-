"use client";

/**
 * Session handling, with the same switch the backend uses.
 *
 *   NEXT_PUBLIC_AUTH_PROVIDER = mock | supabase     (default: mock)
 *
 * `mock` signs in as a demo customer or agent with one click, so the app is
 * still demoable with zero setup (INTENT §5) while genuinely requiring a
 * session — the backend rejects anything that isn't a valid token.
 *
 * `supabase` uses Supabase Auth. Its tokens are verified server-side in
 * `auth.py`; nothing here is trusted.
 */

const TOKEN_KEY = "digital-fte:token";
const ROLE_KEY = "digital-fte:role";

export const AUTH_PROVIDER =
  process.env.NEXT_PUBLIC_AUTH_PROVIDER || "mock";

export const isMockAuth = AUTH_PROVIDER === "mock";

function read(key) {
  if (typeof window === "undefined") return null;   // SSR pass has no storage
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;                                     // private mode
  }
}

function write(key, value) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable — the session lasts for this page view only */
  }
}

export function getToken() {
  return read(TOKEN_KEY);
}

export function getRole() {
  return read(ROLE_KEY);
}

export function isSignedIn() {
  return Boolean(getToken());
}

/** Mock sign-in: pick a role, get a token the backend will accept. */
export function signInAsDemo(role = "customer") {
  const token = `mock:${role}`;
  write(TOKEN_KEY, token);
  write(ROLE_KEY, role);
  return token;
}

/** Supabase email + password. Returns { error } on failure. */
export async function signInWithPassword(email, password) {
  const supabase = await getSupabase();
  if (!supabase) return { error: "Supabase auth is not configured." };

  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { error: error.message };

  return storeSupabaseSession(data.session);
}

export async function signUpWithPassword(email, password) {
  const supabase = await getSupabase();
  if (!supabase) return { error: "Supabase auth is not configured." };

  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) return { error: error.message };
  if (!data.session) {
    // Email confirmation is on for this project.
    return { error: "Check your inbox to confirm the address, then sign in." };
  }
  return storeSupabaseSession(data.session);
}

function storeSupabaseSession(session) {
  if (!session?.access_token) return { error: "No session returned." };
  write(TOKEN_KEY, session.access_token);
  // The role the backend enforces comes from the verified token, never from
  // here — this copy only decides whether to show the Tickets link.
  write(ROLE_KEY, session.user?.app_metadata?.role || "customer");
  return { error: null };
}

export async function signOut() {
  if (!isMockAuth) {
    const supabase = await getSupabase();
    await supabase?.auth.signOut().catch(() => {});
  }
  write(TOKEN_KEY, null);
  write(ROLE_KEY, null);
}

let supabaseClient;

async function getSupabase() {
  if (isMockAuth) return null;
  if (supabaseClient !== undefined) return supabaseClient;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    supabaseClient = null;
    return null;
  }
  const { createClient } = await import("@supabase/supabase-js");
  supabaseClient = createClient(url, anonKey);
  return supabaseClient;
}
