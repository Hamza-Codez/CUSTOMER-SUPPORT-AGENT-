// Base URL of the FastAPI backend. Override in .env.local for deployment.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function sendChat(message, sessionId) {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return res.json();
}

export async function fetchTickets() {
  const res = await fetch(`${API_URL}/tickets`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return res.json();
}
