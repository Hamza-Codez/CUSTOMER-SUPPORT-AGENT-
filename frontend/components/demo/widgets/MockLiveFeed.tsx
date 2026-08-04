import * as React from "react";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function MockLiveFeed({ className }: { className?: string }) {
  const events = [
    { text: "Agent resolved ORD-0995 (Refund)", time: "12s ago", tone: "text-ok" },
    { text: "New query: 'Compare desks'", time: "45s ago", tone: "text-fg" },
    { text: "User escalation to Desk", time: "1m ago", tone: "text-warn" },
    { text: "Inventory alert: A-LITE-W out of stock", time: "3m ago", tone: "text-alert" },
    { text: "Agent deflected shipping query", time: "5m ago", tone: "text-ok" },
  ];

  return (
    <Card className={cn("flex flex-col p-0", className)}>
      <div className="flex justify-between items-center p-3 border-b border-line-soft bg-surface/50">
        <h3 className="text-[12px] font-semibold text-fg">Live Feed</h3>
        <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
      </div>
      <div className="flex flex-col text-[11px] font-mono h-32 overflow-hidden relative">
        {events.map((ev, i) => (
          <div key={i} className="flex gap-3 px-3 py-1.5 border-b border-line-soft/30 hover:bg-raised transition-colors">
            <span className="text-muted w-12 shrink-0">{ev.time}</span>
            <span className={cn("truncate", ev.tone)}>{ev.text}</span>
          </div>
        ))}
        {/* Fade out bottom */}
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-raised to-transparent pointer-events-none" />
      </div>
    </Card>
  );
}
