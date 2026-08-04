import * as React from "react";
import { Card, Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { Truck, Package, RotateCcw } from "lucide-react";

export function MockDeliveryServices({ className }: { className?: string }) {
  const services = [
    { name: "FDX-EX", status: "SYNC", lastSync: "2m" },
    { name: "UPS-GR", status: "SYNC", lastSync: "5m" },
    { name: "USP-RT", status: "DELY", lastSync: "1h" },
  ];

  return (
    <Card className={cn("flex flex-col p-0", className)}>
      <div className="flex justify-between items-center p-3 border-b border-line-soft bg-surface/50">
        <h3 className="text-[12px] font-semibold text-fg">Logistics Net</h3>
      </div>

      <div className="flex flex-col text-[11px] font-mono">
        <div className="flex px-3 py-1.5 text-faint border-b border-line-soft bg-raised/30">
          <span className="flex-1">PROVIDER</span>
          <span className="w-12 text-right">SYNC</span>
          <span className="w-10 text-right">STS</span>
        </div>
        {services.map((service, i) => (
          <div key={i} className={cn("flex px-3 py-1.5 hover:bg-raised transition-colors cursor-default", i !== services.length - 1 && "border-b border-line-soft/50")}>
            <span className="flex-1 text-fg truncate pr-2">{service.name}</span>
            <span className="w-12 text-right text-muted">{service.lastSync}</span>
            <span className={cn(
              "w-10 text-right font-semibold",
              service.status === "SYNC" ? "text-ok" : "text-warn"
            )}>{service.status}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
