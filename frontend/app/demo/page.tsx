"use client";

/**
 * The guided demo playground (SPEC §15).
 *
 * Two rules shape this file:
 *
 * 1. **It runs the real thing.** The tour drives the same ChatWidget and the same
 *    Decision Card the dashboard uses, against the real backend and the seeded
 *    store. Scripting the replies would make a smoother demo that proved nothing.
 * 2. **The visitor drives.** Nothing advances on a timer. Each step does one
 *    thing on a click, and the tour can be skipped outright by anyone returning.
 *
 * It holds both demo tokens because seeing both sides is the point, and doing
 * that in one tab otherwise means signing in and out halfway through.
 */

import {
  ArrowRight,
  Check,
  Headphones,
  RotateCcw,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Wordmark } from "@/components/Brand";
import { ChatWidget, type ChatHandle } from "@/components/ChatWidget";
import { DecisionCardView } from "@/components/DecisionCardView";
import { ToolRack } from "@/components/ToolRack";
import { EmailPreviewPanel } from "@/components/demo/EmailPreviewPanel";
import { MockDashboard } from "@/components/demo/MockDashboard";
import { OpsPeek } from "@/components/demo/OpsPeek";
import { STEPS, type Side } from "@/components/demo/steps";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
} from "@/components/ui/primitives";
import {
  ApiError,
  DEMO_CUSTOMER_TOKEN,
  DEMO_OPERATOR_TOKEN,
  api,
} from "@/lib/api";
import { toolForKind, type ToolId } from "@/lib/tools";
import type { ChatResponse, DecisionCard } from "@/lib/types";
import { cn } from "@/lib/utils";

const DEMO_QUICK_REPLIES = [
  { label: "Track an order", text: "Where is my order ORD-1002?" },
  { label: "Delivery times", text: "How long does dispatch take?" },
  {
    label: "Compare desks",
    text: "Which is better, the AeroDesk Pro or the AeroDesk Lite?",
  },
];

export default function DemoPage() {
  // One conversation for the whole tour, so the agent remembers the identity
  // verified in step 3 when the refund is asked for in step 5.
  const [sessionId] = React.useState(
    () => `demo-${Math.random().toString(36).slice(2, 9)}`,
  );
  const [index, setIndex] = React.useState(0);
  const [completed, setCompleted] = React.useState<Record<string, boolean>>({});
  // The visible side follows the step unless the visitor overrides it, and the
  // override is scoped to the step it was made on. Derived rather than synced in
  // an effect: reaching the Decision Card should flip the window immediately,
  // not one render later.
  const [override, setOverride] = React.useState<{
    index: number;
    side: Side;
  } | null>(null);
  const [touring, setTouring] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [cards, setCards] = React.useState<DecisionCard[]>([]);
  const [used, setUsed] = React.useState<Set<ToolId>>(() => new Set());
  const chat = React.useRef<ChatHandle | null>(null);

  const step = STEPS[index];
  const isDone = completed[step.id];
  const isLast = index === STEPS.length - 1;
  const side: Side =
    override && override.index === index ? override.side : step.side;

  function setSide(next: Side) {
    setOverride({ index, side: next });
  }

  const loadQueue = React.useCallback(async () => {
    try {
      const { escalations } = await api.escalations(
        "pending",
        DEMO_OPERATOR_TOKEN,
      );
      setCards(escalations);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the queue.");
    }
  }, []);

  const showingQueue = side === "seller" && step.id === "decision";

  React.useEffect(() => {
    if (!showingQueue) return;
    let cancelled = false;

    async function fetchQueue() {
      try {
        const { escalations } = await api.escalations(
          "pending",
          DEMO_OPERATOR_TOKEN,
        );
        if (!cancelled) setCards(escalations);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError ? e.message : "Could not load the queue.",
          );
        }
      }
    }

    fetchQueue();
    return () => {
      cancelled = true;
    };
  }, [showingQueue]);

  function markDone() {
    setCompleted((prev) => ({ ...prev, [step.id]: true }));
  }

  React.useEffect(() => {
    if (isDone && !isLast) {
      setIndex((i) => i + 1);
    }
  }, [isDone, isLast]);

  async function performStep() {
    setError(null);

    if (step.tools) {
      setUsed((prev) => {
        const next = new Set(prev);
        for (const tool of step.tools!) next.add(tool);
        return next;
      });
    }

    if (step.send) {
      setBusy(true);
      chat.current?.send(step.send);
      return; // completion is signalled by onExchange, when the agent replies
    }

    if (step.id === "decision") {
      const card = cards[0];
      if (!card) {
        await loadQueue();
        setError(
          "No pending decision found. Run the larger refund step first — that is what creates one.",
        );
        return;
      }
      setBusy(true);
      try {
        await api.decide(
          card.escalation_id,
          "approve",
          undefined,
          DEMO_OPERATOR_TOKEN,
        );
        await loadQueue();
        markDone();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "That did not go through.");
      } finally {
        setBusy(false);
      }
      return;
    }

    markDone(); // ops peek and the closing step are just "look at this"
  }

  function onExchange(response: ChatResponse) {
    setBusy(false);
    markDone();
    // A tool lights up in the rack only because the backend reported it acting.
    setUsed((prev) => {
      const next = new Set(prev);
      for (const action of response.actions) {
        const tool = toolForKind(action.kind);
        if (tool) next.add(tool.id);
      }
      return next;
    });
  }

  function restart() {
    // A full reload, so the session id is regenerated and the agent starts with
    // no memory of the identity verified on the previous run-through.
    window.location.reload();
  }

  return (
    <div className="flex h-dvh flex-col bg-ink">
      <header className="border-b border-line bg-surface/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
          <Wordmark />

          <SideToggle side={side} onChange={setSide} />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl min-w-0 min-h-0 flex-1 flex-col lg:flex-row">
        {/* The stage — always the real component, never a mock-up. */}
        <section className="flex min-w-0 min-h-0 flex-1 flex-col border-line lg:border-r">
          {side === "customer" ? (
            <div className="flex min-h-0 flex-1">
              <div className="min-w-0 flex-1">
                <ChatWidget
                  sessionId={sessionId}
                  token={DEMO_CUSTOMER_TOKEN}
                  quickReplies={DEMO_QUICK_REPLIES}
                  onExchange={onExchange}
                  ref={chat}
                />
              </div>
              {/* What it can reach, lighting up as it reaches. */}
              <aside className="hidden w-64 shrink-0 overflow-y-auto border-l border-line bg-surface/40 px-4 py-5 xl:block">
                <ToolRack used={used} working={busy} />
              </aside>
            </div>
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-5 sm:px-6">
              {step.id === "ops" || completed["ops"] ? (
                <OpsPeek />
              ) : (
                <MockDashboard 
                  operatorQueue={
                    <>
                      {cards.length === 0 ? (
                        <Card>
                          <EmptyState
                            title="Nothing waiting"
                            hint="Ask for a refund above the automatic limit in the customer view, and it will appear here."
                          />
                        </Card>
                      ) : (
                        <div className="flex flex-col gap-3">
                          {cards.map((card) => (
                            <DecisionCardView
                              key={card.escalation_id}
                              card={card}
                              busy={busy}
                              onDecide={async (id, decision, reason) => {
                                setBusy(true);
                                try {
                                  await api.decide(
                                    id,
                                    decision,
                                    reason,
                                    DEMO_OPERATOR_TOKEN,
                                  );
                                  await loadQueue();
                                  if (step.id === "decision") markDone();
                                } finally {
                                  setBusy(false);
                                }
                              }}
                            />
                          ))}
                        </div>
                      )}
                    </>
                  }
                />
              )}
            </div>
          )}
        </section>

        {/* The guide */}
        {touring && side === "customer" && (
          <aside className="flex w-full shrink-0 flex-col border-t border-line bg-surface/40 lg:w-[24rem] lg:border-t-0">
            <div className="flex-1 overflow-y-auto p-4 sm:p-5">
              <Progress index={index} total={STEPS.length} />

              <Card accent className="mt-3 animate-rise">
                <div className="p-5">
                  <div className="mb-2 flex items-center gap-2">
                    <Badge tone="accent">
                      Step {index + 1} of {STEPS.length}
                    </Badge>
                    <Badge tone="neutral">
                      {step.side === "customer" ? "Customer" : "Seller"}
                    </Badge>
                  </div>

                  <h2 className="mb-2 text-[15px] font-semibold text-fg">
                    {step.title}
                  </h2>
                  <p className="text-[13px] leading-relaxed text-muted">
                    {step.body}
                  </p>

                  {step.done && (
                    <p className="mt-3 flex gap-2 rounded-xl border border-ok/25 bg-ok/5 p-3 text-[12px] leading-relaxed text-ok">
                      <Check size={14} className="mt-0.5 shrink-0 opacity-70" />
                      {step.done}
                    </p>
                  )}

                  {step.id === "loop" && isDone && (
                    <div className="mt-3">
                      <EmailPreviewPanel sessionId={sessionId} />
                    </div>
                  )}

                  {error && (
                    <div className="mt-3">
                      <ErrorState message={error} />
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap gap-2">
                    {!isDone && !isLast && (
                      <Button onClick={performStep} disabled={busy}>
                        {busy ? "Working…" : step.action}
                      </Button>
                    )}
                    {isLast && (
                      <>
                        <Link
                          href="/pricing"
                          className="action inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm font-medium transition active:translate-y-px"
                        >
                          See pricing <ArrowRight size={15} />
                        </Link>
                        <Button variant="secondary" onClick={restart}>
                          <RotateCcw size={14} /> Start over
                        </Button>
                      </>
                    )}
                    {!isDone && index > 0 && !isLast && (
                      <Button
                        variant="ghost"
                        onClick={() => setIndex((i) => i + 1)}
                      >
                        Skip
                      </Button>
                    )}
                  </div>

                  <p className="mt-4 border-t border-line-soft pt-3 text-[11px] leading-relaxed text-faint">
                    {step.aha}
                  </p>
                </div>
              </Card>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

function Progress({ index, total }: { index: number; total: number }) {
  return (
    <div className="flex gap-1" aria-label={`Step ${index + 1} of ${total}`}>
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "h-1 flex-1 rounded-full transition",
            i < index ? "bg-accent/50" : i === index ? "bg-accent" : "bg-line",
          )}
        />
      ))}
    </div>
  );
}

function SideToggle({
  side,
  onChange,
}: {
  side: Side;
  onChange: (s: Side) => void;
}) {
  const options: { id: Side; label: string; icon: React.ReactNode }[] = [
    { id: "customer", label: "Storefront", icon: <Headphones size={13} /> },
    { id: "seller", label: "Your desk", icon: <SlidersHorizontal size={13} /> },
  ];
  return (
    <div
      role="tablist"
      aria-label="View"
      className="ml-2 flex rounded-xl border border-line bg-raised p-0.5 shadow-[inset_0_1px_2px_rgb(0_0_0/0.3)]"
    >
      {options.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={side === o.id}
          onClick={() => onChange(o.id)}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition",
            side === o.id ? "bg-ok/20 text-ok shadow-[inset_0_1px_0_0_rgb(255_255_255/0.1)]" : "text-muted hover:text-fg",
          )}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  );
}
