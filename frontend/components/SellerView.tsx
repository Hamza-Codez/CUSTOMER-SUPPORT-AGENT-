"use client";

import { Inbox, RefreshCw, Star } from "lucide-react";
import * as React from "react";

import { DecisionCardView } from "@/components/DecisionCardView";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import type { DecisionCard, FeedbackSummary } from "@/lib/types";

export function SellerView() {
  const [cards, setCards] = React.useState<DecisionCard[] | null>(null);
  const [csat, setCsat] = React.useState<FeedbackSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);

  const [reloads, setReloads] = React.useState(0);
  const load = React.useCallback(() => setReloads((n) => n + 1), []);

  React.useEffect(() => {
    // `cancelled` matters: without it a reply arriving after the operator
    // switches back to the customer view sets state on an unmounted component.
    let cancelled = false;

    async function fetchQueue() {
      try {
        const [queue, feedback] = await Promise.all([
          api.escalations(),
          api.feedback(),
        ]);
        if (cancelled) return;
        setError(null);
        setCards(queue.escalations);
        setCsat(feedback);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError ? e.message : "Could not load the queue.",
        );
        setCards([]);
      }
    }

    fetchQueue();
    // The queue is server state, so poll rather than hold a local copy that
    // drifts from what an operator on another screen already actioned.
    const timer = setInterval(fetchQueue, 10_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [reloads]);

  async function decide(
    id: string,
    decision: "approve" | "decline",
    reason?: string,
  ) {
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.decide(id, decision, reason);
      setNotice(
        result.customer_reply
          ? `${decision === "approve" ? "Approved" : "Declined"} — the customer was told: “${result.customer_reply.slice(0, 120)}”`
          : `${decision === "approve" ? "Approved" : "Declined"}. Outcome: ${result.outcome}.`,
      );
      load();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "That decision did not go through.",
      );
    } finally {
      setBusy(false);
    }
  }

  const pending = (cards ?? []).filter((c) => c.status === "pending");
  const settled = (cards ?? []).filter((c) => c.status !== "pending");

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-fg">Operations</h2>
          <p className="text-[13px] text-faint">
            Decisions the FTE prepared but would not make alone.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={busy}>
          <RefreshCw size={13} className={busy ? "animate-spin" : ""} />
          Refresh
        </Button>
      </div>

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Awaiting you" value={cards ? String(pending.length) : null} />
        <Stat
          label="Satisfaction"
          value={
            csat
              ? csat.average_rating !== null
                ? `${csat.average_rating} / 5`
                : "No replies yet"
              : null
          }
          icon={csat?.average_rating ? <Star size={13} /> : undefined}
        />
        <Stat
          label="Feedback replies"
          value={csat ? String(csat.responses) : null}
        />
      </div>

      {notice && (
        <div className="mb-4 rounded-xl border border-ok/25 bg-ok/5 p-3 text-[13px] text-ok">
          {notice}
        </div>
      )}
      {error && (
        <div className="mb-4">
          <ErrorState message={error} onRetry={load} />
        </div>
      )}

      {cards === null ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-44 w-full rounded-2xl" />
          <Skeleton className="h-44 w-full rounded-2xl" />
        </div>
      ) : pending.length === 0 && settled.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Inbox size={22} />}
            title="No escalations"
            hint="The FTE is handling things. Ask it for an out-of-policy refund in the customer view to see one arrive here."
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {pending.map((card) => (
            <DecisionCardView
              key={card.escalation_id}
              card={card}
              onDecide={decide}
              busy={busy}
            />
          ))}

          {settled.length > 0 && (
            <>
              <p className="mt-4 text-[11px] uppercase tracking-wider text-faint">
                Recently settled
              </p>
              {settled.slice(0, 5).map((card) => (
                <DecisionCardView
                  key={card.escalation_id}
                  card={card}
                  onDecide={decide}
                  busy={busy}
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | null;
  icon?: React.ReactNode;
}) {
  return (
    <Card className="p-4">
      <p className="mb-1.5 text-[11px] uppercase tracking-wider text-faint">
        {label}
      </p>
      {value === null ? (
        <Skeleton className="h-6 w-20" />
      ) : (
        <p className="flex items-center gap-1.5 text-lg font-semibold text-fg">
          {icon && <span className="text-accent">{icon}</span>}
          {value}
        </p>
      )}
    </Card>
  );
}
