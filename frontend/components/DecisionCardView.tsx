"use client";

/**
 * The Decision Card — the "ready to click OK" moment.
 *
 * Everything shown here was produced by a tool during the paused run, never by
 * the model asserting it. That is what makes approving in one click safe, and
 * why the card leads with *why a human was needed* rather than burying it.
 */

import { BadgeCheck, Clock, ShieldAlert } from "lucide-react";
import * as React from "react";

import { Badge, Button, Card } from "@/components/ui/primitives";
import type { DecisionCard } from "@/lib/types";

export function DecisionCardView({
  card,
  onDecide,
  busy,
}: {
  card: DecisionCard;
  onDecide: (
    id: string,
    decision: "approve" | "decline",
    reason?: string,
  ) => void;
  busy: boolean;
}) {
  const [declining, setDeclining] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const pending = card.status === "pending";

  return (
    <Card accent className="animate-rise">
      <div className="p-5">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="mb-1 text-[11px] uppercase tracking-wider text-faint">
              Needs a decision
            </p>
            <h3 className="truncate text-[15px] font-semibold text-fg">
              {card.request}
            </h3>
          </div>
          <StatusBadge status={card.status} />
        </div>

        <dl className="grid gap-3 sm:grid-cols-2">
          <Field label="Customer">
            <span className="flex items-center gap-1.5">
              {card.customer?.name ?? "Unnamed"}
              {card.customer?.verified && (
                <Badge tone="ok">
                  <BadgeCheck size={11} /> verified
                </Badge>
              )}
            </span>
          </Field>

          <Field label="Why it stopped">{card.policy_check?.result ?? "—"}</Field>

          <Field label="Proposed action">
            {card.proposed_action?.amount ? (
              <>
                Refund{" "}
                <span className="font-semibold text-fg">
                  {card.proposed_action.amount}
                </span>{" "}
                for {card.proposed_action.order_id}
              </>
            ) : (
              "Review"
            )}
          </Field>

          <Field label="Order status">
            {card.policy_check?.order_status ?? "—"}
            {card.policy_check?.delivered_on
              ? ` · delivered ${card.policy_check.delivered_on}`
              : ""}
          </Field>
        </dl>

        {!!card.policy_check?.sources?.length && (
          <p className="mt-3 text-[12px] text-faint">
            Policy consulted: {card.policy_check.sources.join(", ")}
          </p>
        )}

        {pending && (
          <div className="mt-5 border-t border-line-soft pt-4">
            {declining ? (
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  autoFocus
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Reason the customer will be given…"
                  aria-label="Reason for declining"
                  className="h-10 flex-1 rounded-xl border border-line bg-raised px-3.5 text-sm text-fg placeholder:text-faint focus:border-accent/60"
                />
                <div className="flex gap-2">
                  <Button
                    variant="danger"
                    disabled={busy || !reason.trim()}
                    onClick={() =>
                      onDecide(card.escalation_id, "decline", reason.trim())
                    }
                  >
                    Confirm decline
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setDeclining(false)}
                    disabled={busy}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={busy}
                  onClick={() => onDecide(card.escalation_id, "approve")}
                >
                  Approve refund
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => setDeclining(true)}
                >
                  Decline…
                </Button>
              </div>
            )}
          </div>
        )}

        {!pending && card.resolved_by && (
          <p className="mt-4 border-t border-line-soft pt-3 text-[12px] text-faint">
            {card.status === "approved" ? "Approved" : "Declined"} by{" "}
            {card.resolved_by}
            {card.resolution_reason ? ` — ${card.resolution_reason}` : ""}
          </p>
        )}
      </div>
    </Card>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="mb-0.5 text-[11px] uppercase tracking-wider text-faint">
        {label}
      </dt>
      <dd className="text-[13px] text-body">{children}</dd>
    </div>
  );
}

function StatusBadge({ status }: { status: DecisionCard["status"] }) {
  if (status === "approved")
    return (
      <Badge tone="ok">
        <BadgeCheck size={11} /> approved
      </Badge>
    );
  if (status === "declined")
    return (
      <Badge tone="alert">
        <ShieldAlert size={11} /> declined
      </Badge>
    );
  return (
    <Badge tone="warn">
      <Clock size={11} /> pending
    </Badge>
  );
}
