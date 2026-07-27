"use client";

/**
 * What the agent actually did, under its reply.
 *
 * Every chip comes from a real tool result on the backend — a chip cannot
 * appear unless the thing it describes happened. That is the whole point: it is
 * how the interface proves an agent ran rather than a canned reply being shown.
 */

import {
  AlertTriangle,
  BadgeCheck,
  BookOpen,
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

import { Badge } from "@/components/ui/primitives";
import type { AgentAction } from "@/lib/types";

type Tone = "neutral" | "accent" | "ok" | "warn" | "alert";

const CHIPS: Record<string, { tone: Tone; icon: React.ReactNode }> = {
  routed: { tone: "neutral", icon: <Route size={12} /> },
  order_looked_up: { tone: "accent", icon: <PackageSearch size={12} /> },
  order_not_found: { tone: "warn", icon: <SearchX size={12} /> },
  identity_check_failed: { tone: "alert", icon: <ShieldAlert size={12} /> },
  policy_cited: { tone: "accent", icon: <BookOpen size={12} /> },
  no_policy_match: { tone: "warn", icon: <SearchX size={12} /> },
  product_viewed: { tone: "accent", icon: <PackageSearch size={12} /> },
  products_compared: { tone: "accent", icon: <PackageSearch size={12} /> },
  no_product_match: { tone: "warn", icon: <SearchX size={12} /> },
  refund_executed: { tone: "ok", icon: <BadgeCheck size={12} /> },
  refund_duplicate: { tone: "neutral", icon: <Undo2 size={12} /> },
  refund_refused: { tone: "alert", icon: <ShieldAlert size={12} /> },
  approval_pending: { tone: "warn", icon: <Clock size={12} /> },
  escalated: { tone: "warn", icon: <AlertTriangle size={12} /> },
  email_sent: { tone: "ok", icon: <Mail size={12} /> },
  email_already_sent: { tone: "neutral", icon: <Mail size={12} /> },
  email_refused: { tone: "warn", icon: <MailX size={12} /> },
  email_failed: { tone: "alert", icon: <MailX size={12} /> },
  blocked: { tone: "alert", icon: <ShieldAlert size={12} /> },
  ungrounded_blocked: { tone: "warn", icon: <ShieldAlert size={12} /> },
  agent_stuck: { tone: "warn", icon: <AlertTriangle size={12} /> },
};

export function ActionChips({ actions }: { actions: AgentAction[] }) {
  if (!actions.length) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {actions.map((action, i) => {
        const chip = CHIPS[action.kind] ?? {
          tone: "neutral" as Tone,
          icon: null,
        };
        return (
          <Badge key={`${action.kind}-${i}`} tone={chip.tone}>
            {chip.icon}
            <span>{action.label}</span>
          </Badge>
        );
      })}
    </div>
  );
}
