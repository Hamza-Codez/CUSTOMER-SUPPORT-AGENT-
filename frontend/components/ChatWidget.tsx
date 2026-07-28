"use client";

import { ArrowUp, RefreshCw } from "lucide-react";
import * as React from "react";

import { ActionChips } from "@/components/ActionChips";
import { Mark } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";
import { brand } from "@/lib/brand";
import type { ChatResponse, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

/** One-tap starters, so the first message is never a blank box. */
const QUICK_REPLIES = [
  { label: "Track an order", text: "Where is my order ORD-1002? My email is ayesha.k@example.com" },
  { label: "Delivery times", text: "How long does dispatch take?" },
  { label: "Compare desks", text: "Which is better, the AeroDesk Pro or the AeroDesk Lite?" },
  { label: "Ask for a refund", text: "I'd like a refund for ORD-1005, email ayesha.k@example.com" },
];

/** Shown in sequence while a turn is in flight.
 *
 * Honest about what it is: the backend answers a turn in one response rather
 * than streaming its steps, so this narrates the shape of the work instead of
 * claiming a specific tool is running right now. The chips that follow are the
 * real record. */
const WORKING_STAGES = [
  "Reading the request",
  "Choosing a specialist",
  "Checking real records",
  "Composing a reply",
];

let counter = 0;
const nextId = () => `m${++counter}`;

export type ChatHandle = { send: (text: string) => void };

export function ChatWidget({
  sessionId,
  token,
  quickReplies,
  onExchange,
  ref,
}: {
  sessionId: string;
  token?: string;
  quickReplies?: { label: string; text: string }[];
  onExchange?: (response: ChatResponse) => void;
  ref?: React.Ref<ChatHandle>;
}) {
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
      const response = await api.chat(trimmed, sessionId, token);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholder.id
            ? { ...m, pending: false, text: response.reply, actions: response.actions }
            : m,
        ),
      );
      onExchange?.(response);
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

  React.useImperativeHandle(ref, () => ({ send }));

  const chips = quickReplies ?? QUICK_REPLIES;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        {messages.length === 0 ? <Welcome /> : (
          <div className="mx-auto flex max-w-2xl flex-col gap-5">
            {messages.map((message) => (
              <Bubble key={message.id} message={message} />
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-line bg-surface/60 px-4 py-3.5 backdrop-blur sm:px-6">
        <div className="mx-auto max-w-2xl">
          <div className="mb-2.5 flex flex-wrap gap-1.5">
            {chips.map((chip) => (
              <button
                key={chip.label}
                onClick={() => send(chip.text)}
                disabled={busy}
                className={cn(
                  "rounded-lg border border-line bg-raised/70 px-3 py-1.5 text-[12px] text-muted",
                  "transition hover:border-accent/45 hover:text-fg active:translate-y-px",
                  "disabled:opacity-40",
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
            className={cn(
              "flex items-center gap-2 rounded-2xl border border-line bg-raised p-1.5",
              "shadow-[inset_0_1px_2px_rgb(0_0_0/0.35)] transition focus-within:border-accent/50",
            )}
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={busy}
              placeholder="Ask about an order, a refund, a product…"
              aria-label="Message"
              className="h-9 flex-1 bg-transparent px-3 text-sm text-fg outline-none placeholder:text-faint"
            />
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              aria-label="Send"
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition",
                "action",
                "active:translate-y-px",
                "disabled:bg-elevated disabled:bg-none disabled:text-faint disabled:shadow-none",
              )}
            >
              {busy ? (
                <RefreshCw size={15} className="animate-spin" />
              ) : (
                <ArrowUp size={16} />
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Welcome() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center pt-12 text-center">
      <Mark size={44} className="mb-4" />
      <h2 className="text-heading text-fg">Your employee is on shift</h2>
      <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
        {brand.promise}
      </p>
      <p className="mt-4 text-[12px] text-faint">
        Everything below the replies is a record of what it actually did.
      </p>
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex animate-rise justify-end">
        <div className="max-w-[82%] rounded-2xl rounded-br-md border border-accent/25 bg-accent/[0.13] px-4 py-2.5 text-sm leading-relaxed text-fg">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex animate-rise gap-3">
      <span className="mt-0.5 shrink-0">
        <Mark size={26} />
      </span>
      <div className="min-w-0 flex-1">
        <div
          className={cn(
            "rounded-2xl rounded-tl-md border px-4 py-2.5 text-sm leading-relaxed",
            message.failed
              ? "border-alert/30 bg-alert/[0.06] text-alert"
              : "border-line bg-surface text-body",
          )}
        >
          {message.pending ? <Working /> : message.text}
        </div>
        {message.actions && <ActionChips actions={message.actions} />}
      </div>
    </div>
  );
}

/** The waiting state, narrating the shape of the work rather than pretending to
 * know which tool is running. The chips afterwards are the real record.
 *
 * Past the last stage it switches to a clock. The previous version clamped at
 * "Composing a reply…" and sat there indefinitely, which turned a slow turn into
 * something indistinguishable from a hang — the exact complaint that prompted
 * this. Counting seconds is less reassuring and more true. */
function Working() {
  const [elapsed, setElapsed] = React.useState(0);

  React.useEffect(() => {
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      500,
    );
    return () => clearInterval(timer);
  }, []);

  const stage = Math.floor(elapsed / 1.2);
  const narrating = stage < WORKING_STAGES.length;
  const label = narrating
    ? `${WORKING_STAGES[stage]}…`
    : elapsed < 20
      ? `Still working — ${elapsed}s`
      : `Still working — ${elapsed}s. It may be starting up, or rate-limited.`;

  return (
    <div className="flex flex-col gap-2 py-0.5">
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="typing-dot h-1.5 w-1.5 rounded-full bg-accent-soft"
              style={{ animationDelay: `${i * 0.16}s` }}
            />
          ))}
        </span>
        <span
          key={narrating ? stage : "elapsed"}
          className="animate-slide-in text-[12.5px] text-muted"
          aria-live="polite"
        >
          {label}
        </span>
      </div>
      <span className="relative h-px w-full overflow-hidden rounded bg-line">
        <span className="absolute inset-y-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-accent to-transparent" />
      </span>
    </div>
  );
}
