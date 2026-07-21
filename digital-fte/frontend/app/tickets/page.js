"use client";
import { useEffect, useState } from "react";
import { fetchTickets } from "../api";

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const data = await fetchTickets();
      setTickets(data.tickets);
      setErr("");
    } catch (e) {
      setErr(e.message + " — is the backend running on :8000?");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 3000); // live refresh
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h2>Agent work log — tickets</h2>
      <p className="hint">Auto-refreshes every 3s. Tickets are created by the agent as it works.</p>
      {err && <p className="empty">⚠️ {err}</p>}
      {!err && tickets.length === 0 && (
        <p className="empty">No tickets yet. Ask the agent to process a refund or escalate something.</p>
      )}
      {tickets.map((t) => (
        <div className="ticket" key={t.id}>
          <div className="row">
            <span className="id">{t.id} — {t.subject}</span>
            <span className={`badge ${t.priority === "high" ? "high" : "normal"}`}>
              {t.escalated ? "escalated" : t.priority}
            </span>
          </div>
          <div className="detail">{t.detail}</div>
          <div className="meta">
            {t.order_id ? `Order ${t.order_id} · ` : ""}status: {t.status} · {t.created_at}
          </div>
        </div>
      ))}
    </div>
  );
}
