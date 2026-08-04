import * as React from "react";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function MockStatsChart({ className }: { className?: string }) {
  // Mock data for a generic performance chart
  const data = [
    { label: "Mon", active: 45, deflected: 32 },
    { label: "Tue", active: 52, deflected: 38 },
    { label: "Wed", active: 49, deflected: 41 },
    { label: "Thu", active: 61, deflected: 49 },
    { label: "Fri", active: 58, deflected: 50 },
    { label: "Sat", active: 30, deflected: 28 },
    { label: "Sun", active: 35, deflected: 31 },
  ];

  const max = 70; // Fixed max for scale

  return (
    <Card className={cn("p-3 flex flex-col gap-2", className)}>
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-[12px] font-semibold text-fg">AI Performance</h3>
        </div>
        <div className="flex items-center gap-2">
          <p className="text-[10px] text-ok uppercase tracking-wider">Deflection</p>
          <p className="text-[14px] font-mono text-accent">82.1%</p>
        </div>
      </div>

      <div className="flex-1 flex items-end justify-between gap-1.5 mt-2 pt-2 border-t border-line-soft">
        {data.map((day, i) => (
          <div key={i} className="flex flex-col items-center gap-1 w-full">
            <div className="relative w-full h-16 bg-raised rounded-sm overflow-hidden flex flex-col justify-end">
              {/* Human (Active - Deflected) */}
              <div
                className="w-full bg-line-lit transition-all duration-500"
                style={{ height: `${(day.active / max) * 100}%` }}
              >
                {/* AI (Deflected) */}
                <div
                  className="w-full bg-accent/80 transition-all duration-500"
                  style={{ height: `${(day.deflected / day.active) * 100}%` }}
                />
              </div>
            </div>
            <span className="text-[9px] text-muted">{day.label}</span>
          </div>
        ))}
      </div>
      
      <div className="flex gap-3 text-[9px] text-muted mt-1">
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-accent/80" />
          <span>Automated</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-line-lit" />
          <span>Escalated</span>
        </div>
      </div>
    </Card>
  );
}
