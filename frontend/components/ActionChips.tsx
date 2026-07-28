"use client";

/**
 * What the agent actually did, under its reply.
 *
 * Every chip comes from a real tool result on the backend — a chip cannot appear
 * unless the thing it names happened. They reveal in sequence because that is
 * the order the tools ran in, so the animation is showing you real events rather
 * than dressing up a single response.
 */

import {
  AlertTriangle,
  BadgeCheck,
  BookOpen,
  Boxes,
  Clock,
  Mail,
  MailX,
  PackageSearch,
  Route,
  SearchX,
  ShieldAlert,
  Undo2,
} from "lucide-react";
import * as React from "react";

import type { AgentAction } from "@/lib/types";
import { verdictFor } from "@/lib/tools";
import { cn } from "@/lib/utils";

const ICONS: Record<string, React.ReactNode> = {
  routed: <Route size={11} />,
  order_looked_up: <PackageSearch size={11} />,
  order_not_found: <SearchX size={11} />,
  identity_check_failed: <ShieldAlert size={11} />,
  policy_cited: <BookOpen size={11} />,
  no_policy_match: <SearchX size={11} />,
  product_viewed: <Boxes size={11} />,
  products_compared: <Boxes size={11} />,
  no_product_match: <SearchX size={11} />,
  refund_executed: <BadgeCheck size={11} />,
  refund_duplicate: <Undo2 size={11} />,
  refund_refused: <ShieldAlert size={11} />,
  approval_pending: <Clock size={11} />,
  escalated: <AlertTriangle size={11} />,
  email_sent: <Mail size={11} />,
  email_already_sent: <Mail size={11} />,
  email_refused: <MailX size={11} />,
  email_failed: <MailX size={11} />,
  blocked: <ShieldAlert size={11} />,
  ungrounded_blocked: <ShieldAlert size={11} />,
  agent_stuck: <AlertTriangle size={11} />,
};

const TONE = {
  ok: "border-ok/25 bg-ok/[0.08] text-ok",
  held: "border-warn/25 bg-warn/[0.08] text-warn",
  blocked: "border-alert/25 bg-alert/[0.08] text-alert",
  neutral: "border-line bg-raised text-muted",
} as const;

export function ActionChips({ actions }: { actions: AgentAction[] }) {
  if (!actions.length) return null;

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      {actions.map((action, i) => (
        <span
          key={`${action.kind}-${i}`}
          className={cn(
            "inline-flex animate-slide-in items-center gap-1.5 rounded-lg border px-2 py-1",
            "text-[11px] font-medium leading-none",
            TONE[verdictFor(action.kind)],
          )}
          // Sequenced, because the tools genuinely ran in this order.
          style={{ animationDelay: `${i * 90}ms` }}
          title={action.ref ?? undefined}
        >
          {ICONS[action.kind]}
          <span>{action.label}</span>
        </span>
      ))}
    </div>
  );
}
