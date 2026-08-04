import * as React from "react";
import { cn } from "@/lib/utils";

export function MockTicker({ className }: { className?: string }) {
  return (
    <div className={cn("overflow-hidden w-full min-w-0 border-b border-line-soft bg-ink text-[11px] font-mono whitespace-nowrap py-1.5 flex items-center", className)}>
      <div className="mx-auto max-w-7xl w-full min-w-0 overflow-hidden">
        <div className="animate-[ticker_30s_linear_infinite] flex gap-8">
        {[...Array(3)].map((_, i) => (
          <React.Fragment key={i}>
            <span className="text-muted"><span className="text-ok">↑</span> ACTIVE_CHATS: <span className="text-fg">142</span></span>
            <span className="text-muted"><span className="text-warn">~</span> QUEUE_DEPTH: <span className="text-fg">14</span></span>
            <span className="text-muted"><span className="text-ok">↑</span> GSAT_SCORE: <span className="text-fg">94.2%</span></span>
            <span className="text-muted"><span className="text-accent">↑</span> REV_SAVED: <span className="text-fg">$4,120</span></span>
            <span className="text-muted"><span className="text-alert">↓</span> AVG_HANDLE: <span className="text-fg">2m14s</span></span>
            <span className="text-muted"><span className="text-ok">↑</span> DEFLECTION: <span className="text-fg">82.1%</span></span>
            <span className="text-muted"><span className="text-ok">↑</span> API_HEALTH: <span className="text-fg">99.9%</span></span>
          </React.Fragment>
        ))}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes ticker {
          0% { transform: translateX(0); }
          100% { transform: translateX(-32.33%); }
        }
      `}} />
      </div>
    </div>
  );
}
