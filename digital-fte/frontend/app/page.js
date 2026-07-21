"use client";
import { useState, useRef, useEffect } from "react";
import { sendChat } from "./api";

const SESSION_ID = "web-" + Math.random().toString(36).slice(2, 8);

export default function ChatPage() {
  const [messages, setMessages] = useState([
    { role: "agent", text: "Hi! I'm your support agent. Ask about products, shipping, or an order (try ORD-1001, ORD-1002, ORD-1003)." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const data = await sendChat(text, SESSION_ID);
      setMessages((m) => [...m, { role: "agent", text: data.reply }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "agent", text: "⚠️ " + e.message + " — is the backend running on :8000?" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">
      <p className="hint">Try: "How long does shipping take?" · "Track ORD-1001" · "Refund ORD-1002, arrived damaged" · "Refund ORD-1003"</p>
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.text}</div>
        ))}
        {loading && <div className="msg agent">…thinking</div>}
        <div ref={endRef} />
      </div>
      <div className="inputrow">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type a customer message…"
        />
        <button onClick={send} disabled={loading}>Send</button>
      </div>
    </div>
  );
}
