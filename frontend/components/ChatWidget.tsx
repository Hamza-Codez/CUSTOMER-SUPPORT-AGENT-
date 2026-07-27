"use client";

import { CornerDownLeft, RefreshCw } from "lucide-react";
import * as React from "react";

import { ActionChips } from "@/components/ActionChips";
import { Button } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import type { Message } from "@/lib/types";
import { cn } from "@/lib/utils";

/** One-tap starters, so the first message is never a blank box. */
const QUICK_REPLIES = [
  "Where is my order ORD-1002? My email is ayesha.k@example.com",
  "How long does dispatch take?",
  "Compare the AeroDesk Pro and the AeroDesk Lite",
  "I'd like a refund for ORD-1005, email ayesha.k@example.com",
];

const QUICK_LABELS = [
  "Track an order",
  "Delivery times",
  "Compare products",
  "Request a refund",
];

let counter = 0;
const nextId = () => `m${++counter}`;

export function ChatWidget({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const endRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    const userMessage: Message = { id: nextId(), role: "user", text: trimmed };
    const placeholder: Message = {
      id: nextId(),
      role: "agent",
      text: "",
      pending: true,
    };
    setMessages((prev) => [...prev, userMessage, placeholder]);
    setDraft("");
    setBusy(true);

    try {
      const response = await api.chat(trimmed, sessionId);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholder.id
            ? {
                ...m,
                pending: false,
                text: response.reply,
                actions: response.actions,
              }
            : m,
        ),
      );
    } catch (error) {
      const detail =
        error instanceof ApiError ? error.message : "Something went wrong.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholder.id
            ? { ...m, pending: false, failed: true, text: detail }
            : m,
        ),
      );
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {messages.length === 0 ? (
          <div className="mx-auto flex max-w-md flex-col items-center gap-2 pt-10 text-center">
            <div className="mb-1 flex h-11 w-11 items-center justify-center rounded-2xl bg-accent/12 text-accent">
              <span className="text-lg font-semibold">F</span>
            </div>
            <h2 className="text-[15px] font-semibold text-fg">
              Your digital employee is on shift
            </h2>
            <p className="text-[13px] leading-relaxed text-faint">
              Ask about an order, a policy, a product, or a refund. Everything it
              tells you comes from real records — never a guess.
            </p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.map((message) => (
              <Bubble key={message.id} message={message} />
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-line bg-surface/60 px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-2xl">
          <div className="mb-2.5 flex flex-wrap gap-1.5">
            {QUICK_REPLIES.map((reply, i) => (
              <button
                key={reply}
                onClick={() => send(reply)}
                disabled={busy}
                className={cn(
                  "rounded-full border border-line bg-raised px-3 py-1.5 text-[12px] text-muted transition",
                  "hover:border-accent/50 hover:text-fg disabled:opacity-40",
                )}
              >
                {QUICK_LABELS[i]}
              </button>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
            className="flex items-center gap-2"
          >
            <div className="relative flex-1">
              <input
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={busy}
                placeholder="Ask about an order, a refund, a product…"
                aria-label="Message"
                className={cn(
                  "h-11 w-full rounded-xl border border-line bg-raised pl-4 pr-10 text-sm text-fg",
                  "placeholder:text-faint transition focus:border-accent/60 disabled:opacity-60",
                )}
              />
              <CornerDownLeft
                size={14}
                className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-faint"
              />
            </div>
            <Button type="submit" disabled={busy || !draft.trim()}>
              {busy ? <RefreshCw size={15} className="animate-spin" /> : "Send"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex animate-rise",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div className={cn("max-w-[85%]", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-accent/15 text-fg border border-accent/25"
              : "border border-line bg-surface text-body",
            message.failed && "border-alert/30 bg-alert/5 text-alert",
          )}
        >
          {message.pending ? <Typing /> : message.text}
        </div>
        {message.actions && <ActionChips actions={message.actions} />}
      </div>
    </div>
  );
}

function Typing() {
  return (
    <span className="flex items-center gap-1 py-1" aria-label="Thinking">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="typing-dot h-1.5 w-1.5 rounded-full bg-accent-soft"
          style={{ animationDelay: `${i * 0.16}s` }}
        />
      ))}
    </span>
  );
}
