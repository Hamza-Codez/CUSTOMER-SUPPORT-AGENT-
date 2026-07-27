"use client";

import {
  BookOpen,
  Boxes,
  Lock,
  Mail,
  PackageSearch,
  Route,
  ShieldAlert,
  Undo2,
} from "lucide-react";
import * as React from "react";

import { TOOLS, type ToolId } from "@/lib/tools";
import { cn } from "@/lib/utils";

const ICONS: Record<ToolId, React.ReactNode> = {
  route: <Route size={14} />,
  order_lookup: <PackageSearch size={14} />,
  policy_retriever: <BookOpen size={14} />,
  product_catalog: <Boxes size={14} />,
  refund_processor: <Undo2 size={14} />,
  human_escalation: <ShieldAlert size={14} />,
  send_summary_email: <Mail size={14} />,
};

/**
 * The agent's actual capabilities, visible while it works.
 *
 * This is the difference between a chat box and something that reads as an
 * employee: you can see what it is able to do, which of those it has just done,
 * and which ones it is not allowed to do alone. A tool lights up only because
 * the backend reported it acting — nothing here is decorative.
 */
export function ToolRack({
  used,
  working = false,
  className,
}: {
  /** Tool ids that have acted in this conversation. */
  used: Set<ToolId>;
  /** True while a turn is in flight. */
  working?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-center gap-2">
        <p className="text-label uppercase text-faint">Capabilities</p>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-[11px]",
            working ? "text-accent-soft" : "text-faint",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              working ? "animate-working bg-accent" : "bg-ok",
            )}
          />
          {working ? "working" : "on shift"}
        </span>
      </div>

      <ul className="flex flex-col gap-1">
        {TOOLS.map((tool) => {
          const active = used.has(tool.id);
          return (
            <li key={tool.id}>
              <div
                className={cn(
                  "group flex items-center gap-2.5 rounded-xl border px-2.5 py-2 transition",
                  active
                    ? "border-accent/30 bg-accent/[0.07]"
                    : "border-transparent hover:border-line hover:bg-raised/60",
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition",
                    active
                      ? "border-accent/40 bg-accent/15 text-accent-soft"
                      : "border-line bg-raised text-faint",
                  )}
                >
                  {ICONS[tool.id]}
                </span>

                <span className="min-w-0 flex-1">
                  <span
                    className={cn(
                      "block truncate text-[12.5px] font-medium transition",
                      active ? "text-fg" : "text-muted",
                    )}
                  >
                    {tool.name}
                  </span>
                  <span className="block truncate text-[11px] text-faint">
                    {active ? "used in this conversation" : tool.blurb}
                  </span>
                </span>

                {tool.gated && (
                  <span
                    title="Gated — limits enforced in code, not by the model"
                    className="shrink-0 text-faint"
                  >
                    <Lock size={11} />
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-1 flex items-start gap-1.5 border-t border-line-soft pt-3 text-[11px] leading-relaxed text-faint">
        <Lock size={11} className="mt-0.5 shrink-0" />
        Gated tools cannot act alone. The cap and the policy window live in code,
        where the model cannot argue with them.
      </p>
    </div>
  );
}
