import * as React from "react";
import { MockStatsChart } from "./widgets/MockStatsChart";
import { MockOrdersList } from "./widgets/MockOrdersList";
import { MockCalendar } from "./widgets/MockCalendar";
import { MockInventory } from "./widgets/MockInventory";
import { MockDeliveryServices } from "./widgets/MockDeliveryServices";
import { MockAdminControls } from "./widgets/MockAdminControls";
import { MockTicker } from "./widgets/MockTicker";
import { MockLiveFeed } from "./widgets/MockLiveFeed";
import { cn } from "@/lib/utils";

export function MockDashboard({
  operatorQueue,
}: {
  operatorQueue: React.ReactNode;
}) {
  return (
    <div className="flex flex-col h-full w-full min-w-0 bg-ink animate-rise overflow-x-hidden">
      {/* Top Ticker */}
      <MockTicker />

      {/* Main Terminal Layout - Asymmetrical Columns */}
      <div className="mx-auto max-w-7xl w-full min-w-0 grid grid-cols-1 lg:grid-cols-[35fr_65fr] gap-6 mt-4">
        
        {/* LEFT OUTLET */}
        <div className="flex flex-col gap-6 min-w-0">
          <div className="flex flex-col gap-6">
            <MockStatsChart />
            <MockAdminControls />
          </div>
          
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 px-2 border-b border-line-soft pb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-alert animate-pulse" />
              <h2 className="text-[11px] font-mono font-semibold text-fg tracking-wider uppercase">Action Required / Queue</h2>
            </div>
            <div className="bg-surface/30 border border-line-soft rounded-sm p-3">
              {operatorQueue}
            </div>
          </div>
          
          <MockLiveFeed />
        </div>

        {/* RIGHT OUTLET */}
        <div className="flex flex-col gap-6 min-w-0">
          <MockOrdersList />
          
          <div className="flex flex-col gap-6">
            <MockInventory />
            <MockDeliveryServices />
          </div>
          
          <MockCalendar />
        </div>

      </div>
    </div>
  );
}
