import * as React from "react";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function MockCalendar({ className }: { className?: string }) {
  const events = [
    { time: "09:00", title: "Morning Sync", type: "meeting" },
    { time: "11:30", title: "Review Escalations", type: "task" },
    { time: "14:00", title: "Vendor Call (Aero)", type: "meeting" },
  ];

  return (
    <Card className={cn("flex flex-col p-0", className)}>
      <div className="flex justify-between items-center p-3 border-b border-line-soft bg-surface/50">
        <h3 className="text-[12px] font-semibold text-fg">Today's Schedule</h3>
      </div>

      <div className="flex flex-col gap-3 p-3 relative text-[11px] font-mono">
        {/* Timeline line */}
        <div className="absolute left-10 top-3 bottom-3 w-px bg-line-soft" />

        {events.map((event, i) => (
          <div key={i} className="flex gap-4 items-start relative z-10">
            <span className="text-faint w-8 text-right shrink-0 mt-0.5">{event.time}</span>
            <div className="relative flex-1">
              <div className={cn(
                "w-2 h-2 rounded-full absolute -left-[20px] top-1",
                event.type === "meeting" ? "bg-accent" : "bg-ok"
              )} />
              <div className="bg-raised/50 px-2 py-1 border border-line-soft/50">
                <span className="text-fg">{event.title}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
