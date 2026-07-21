"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, ArrowUp, RotateCcw } from "lucide-react";

import { AuthError, fetchMe, streamChat } from "./api";
import { isSignedIn } from "./auth";
import { loadSessionId, resetSessionId } from "./session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// The agent's actions, named for a customer rather than for a developer.
const TOOL_LABELS = {
  search_kb: "Searched knowledge base",
  track_order: "Looked up order",
  process_refund: "Processed refund",
  create_ticket: "Opened ticket",
  escalate_to_human: "Escalated to a human",
};

const GREETING = {
  role: "agent",
  text: "Hi — I'm your support agent. Ask about products, shipping or warranty, track an order, or request a refund.",
  tools: [],
};

/** Suggestions built from the user's OWN orders, so every one of them works. */
function suggestionsFor(orders) {
  const refundable = orders.find((o) => o.refundable);
  const blocked = orders.find((o) => !o.refundable);
  return [
    "How long does shipping take?",
    orders[0] && `Track ${orders[0].order_id}`,
    refundable && `Refund ${refundable.order_id}, arrived damaged`,
    blocked && `Refund ${blocked.order_id}`,
  ].filter(Boolean);
}

export default function ChatPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState(null);
  const [me, setMe] = useState(null);
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [actedOnce, setActedOnce] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  // Gate: no session, no chat. The backend would refuse anyway (401) — this
  // just avoids showing a chat box that can't work.
  useEffect(() => {
    if (!isSignedIn()) {
      router.replace("/signin");
      return;
    }
    setSessionId(loadSessionId());
    fetchMe()
      .then(setMe)
      .catch((e) => {
        if (e instanceof AuthError) router.replace("/signin");
        else setError(e.message);
      });
  }, [router]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  const send = useCallback(
    async (text) => {
      const message = (text ?? input).trim();
      if (!message || streaming || !sessionId) return;

      setInput("");
      setError(null);
      setMessages((m) => [...m, { role: "user", text: message }]);
      setStreaming(true);

      // The agent bubble is appended empty and filled as tokens arrive.
      let index = -1;
      setMessages((m) => {
        index = m.length;
        return [...m, { role: "agent", text: "", tools: [] }];
      });

      const patch = (fn) =>
        setMessages((m) => m.map((msg, i) => (i === index ? fn(msg) : msg)));

      try {
        await streamChat(message, sessionId, (event) => {
          if (event.type === "token") {
            patch((msg) => ({ ...msg, text: msg.text + event.text }));
          } else if (event.type === "tool") {
            patch((msg) => ({ ...msg, tools: [...msg.tools, event.name] }));
            if (event.name !== "search_kb") setActedOnce(true);
          } else if (event.type === "error") {
            setError(event.detail);
            patch((msg) => ({ ...msg, failed: true }));
          }
        });
      } catch (e) {
        if (e instanceof AuthError) {
          router.replace("/signin");
          return;
        }
        setError(e.message);
        patch((msg) => ({ ...msg, failed: true }));
      } finally {
        setStreaming(false);
        setMessages((m) =>
          m.filter((msg, i) => i !== index || msg.text || msg.tools.length)
        );
        inputRef.current?.focus();
      }
    },
    [input, streaming, sessionId, router]
  );

  function startOver() {
    setSessionId(resetSessionId());
    setMessages([GREETING]);
    setError(null);
    setActedOnce(false);
    inputRef.current?.focus();
  }

  const suggestions = me ? suggestionsFor(me.orders) : [];

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {me
            ? suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={streaming}
                  className="rounded-full border border-base-line bg-base-800 px-3 py-1 text-xs text-ink-muted transition-colors hover:border-accent-600 hover:text-accent-400 disabled:opacity-40"
                >
                  {s}
                </button>
              ))
            : [56, 92, 120].map((w) => (
                <Skeleton key={w} className="h-6 rounded-full" style={{ width: w }} />
              ))}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={startOver}
          disabled={streaming}
          title="Start a new conversation"
          className="shrink-0"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden />
          New
        </Button>
      </div>

      <div className="grid-backdrop scroll-slim flex-1 space-y-4 overflow-y-auto rounded-2xl border border-base-line bg-base-800/40 p-4">
        {messages.map((m, i) => (
          <Message key={i} message={m} />
        ))}
        {/* Only until the first token lands — after that the text itself is the
            progress indicator, and two of them would compete. */}
        {streaming && !messages[messages.length - 1]?.text && <TypingIndicator />}
        <div ref={endRef} />
      </div>

      {/* Onboarding closes once the agent has completed one real action.
          Agents get the dashboard link; customers can't open it (403), so they
          get the confirmation without a link that would refuse them. */}
      {actedOnce && (
        me?.user.role === "agent" ? (
          <Link
            href="/tickets"
            className="mt-3 flex items-center justify-between rounded-xl border border-accent-700/50 bg-accent-soft px-3 py-2 text-sm text-accent-400 transition-colors hover:border-accent-600"
          >
            That action was logged — see the ticket it just created
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        ) : (
          <p className="mt-3 rounded-xl border border-accent-700/50 bg-accent-soft px-3 py-2 text-sm text-accent-400">
            That action was logged to your account. A support agent can see it on
            their dashboard.
          </p>
        )
      )}

      {error && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-xl border border-high-line bg-high-bg px-3 py-2 text-sm text-high-fg"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {error}
        </p>
      )}

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <Input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={sessionId ? "Type a customer message…" : "Connecting…"}
          disabled={!sessionId}
          aria-label="Message"
        />
        <Button type="submit" size="icon" disabled={streaming || !input.trim()} aria-label="Send">
          <ArrowUp className="h-4 w-4" aria-hidden />
        </Button>
      </form>
    </div>
  );
}

function Message({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex animate-fade-up", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[82%] space-y-2", isUser && "flex flex-col items-end")}>
        {/* Action chips sit above the reply — the agent shows its work. */}
        {message.tools?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.tools.map((tool, i) => (
              <Badge key={i} tone={tool === "escalate_to_human" ? "high" : "accent"}>
                {TOOL_LABELS[tool] || tool}
              </Badge>
            ))}
          </div>
        )}
        {message.text && (
          <div
            className={cn(
              "whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
              isUser
                ? "bg-accent-600 text-white"
                : "border border-base-line bg-base-700 text-ink",
              message.failed && "border-high-line"
            )}
          >
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start" aria-live="polite" aria-label="Agent is replying">
      <div className="flex gap-1 rounded-2xl border border-base-line bg-base-700 px-4 py-3">
        {[0, 200, 400].map((delay) => (
          <span
            key={delay}
            className="h-1.5 w-1.5 animate-blink rounded-full bg-ink-faint"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
