"use client";

import { Info } from "lucide-react";
import * as React from "react";

import { Card, ErrorState, Skeleton } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import type { Analytics } from "@/lib/types";

/**
 * The success signals from SPEC §16.5.
 *
 * A metric with nothing behind it renders as an em dash, never as 0% or £0.00.
 * "100% deflection" from zero conversations is not a good number, it is an
 * absent one, and a dashboard that shows them the same way will be believed at
 * the wrong moment.
 */
export function AnalyticsPanel({ token }: { token?: string }) {
  const [data, setData] = React.useState<Analytics | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    api
      .analytics(token)
      .then((d) => !cancelled && setData(d))
      .catch(
        (e) =>
          !cancelled &&
          setError(
            e instanceof ApiError ? e.message : "Could not load analytics.",
          ),
      );
    return () => {
      cancelled = true;
    };
  }, [attempt, token]);

  if (error)
    return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />;

  if (!data)
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-2xl" />
        ))}
      </div>
    );

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Deflection"
          value={percent(data.deflection_rate)}
          hint={`${data.conversations - data.escalated_conversations} of ${data.conversations} handled alone`}
        />
        <Metric
          label="Approved as prepared"
          value={percent(data.handoff_approval_rate)}
          hint={
            data.handoff_approval_rate === null
              ? "No decisions settled yet"
              : `${data.escalations.approved ?? 0} approved, ${data.escalations.declined ?? 0} declined`
          }
        />
        <Metric
          label="Satisfaction"
          value={data.csat_average === null ? null : `${data.csat_average} / 5`}
          hint={`${data.csat_responses} ${data.csat_responses === 1 ? "reply" : "replies"}`}
        />
        <Metric
          label="Cost per conversation"
          value={
            data.cost_per_conversation === null
              ? null
              : data.cost_per_conversation.toFixed(4)
          }
          hint={
            data.cost_note ??
            `${data.tokens_per_conversation ?? 0} tokens per conversation`
          }
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Small label="Conversations" value={data.conversations} />
        <Small label="Refunds issued" value={data.refunds_executed} />
        <Small label="Awaiting a decision" value={data.escalations.pending ?? 0} />
      </div>

      {data.cost_note && (
        <p className="flex items-start gap-2 text-[12px] leading-relaxed text-faint">
          <Info size={13} className="mt-0.5 shrink-0" />
          {data.cost_note}
        </p>
      )}
    </div>
  );
}

/** `null` renders as an em dash — the honest rendering of "no data yet". */
function percent(value: number | null): string | null {
  return value === null ? null : `${Math.round(value * 100)}%`;
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | null;
  hint?: string;
}) {
  return (
    <Card className="p-4">
      <p className="mb-1.5 text-[11px] uppercase tracking-wider text-faint">
        {label}
      </p>
      <p
        className={`text-xl font-semibold ${value === null ? "text-faint" : "text-fg"}`}
      >
        {value ?? "—"}
      </p>
      {hint && <p className="mt-1 text-[11px] leading-relaxed text-faint">{hint}</p>}
    </Card>
  );
}

function Small({ label, value }: { label: string; value: number }) {
  return (
    <Card className="flex items-center justify-between p-3.5">
      <span className="text-[12px] text-muted">{label}</span>
      <span className="text-sm font-semibold text-fg">{value}</span>
    </Card>
  );
}
