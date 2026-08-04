import * as React from "react";
import { Card, Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function MockInventory({ className }: { className?: string }) {
  const inventory = [
    { sku: "A-PRO-B", stock: 4, vel: "2.1/h", sts: "LOW" },
    { sku: "A-LITE-W", stock: 0, vel: "0.0/h", sts: "OUT" },
    { sku: "ERGO-V2", stock: 12, vel: "0.5/h", sts: "OK" },
    { sku: "MON-ARM", stock: 3, vel: "1.2/h", sts: "LOW" },
    { sku: "CBL-MNG", stock: 45, vel: "5.4/h", sts: "OK" },
  ];

  return (
    <Card className={cn("flex flex-col p-0", className)}>
      <div className="flex justify-between items-center p-3 border-b border-line-soft bg-surface/50">
        <h3 className="text-[12px] font-semibold text-fg">Inventory Matrix</h3>
      </div>
      <div className="flex flex-col text-[11px] font-mono">
        <div className="flex px-3 py-1.5 text-faint border-b border-line-soft bg-raised/30">
          <span className="flex-1">SKU</span>
          <span className="w-12 text-right">STK</span>
          <span className="w-14 text-right">VEL</span>
          <span className="w-12 text-right">STS</span>
        </div>
        {inventory.map((item, i) => (
          <div key={i} className={cn("flex px-3 py-1.5 hover:bg-raised transition-colors cursor-default", i !== inventory.length - 1 && "border-b border-line-soft/50")}>
            <span className="flex-1 text-fg truncate pr-2">{item.sku}</span>
            <span className="w-12 text-right text-muted">{item.stock}</span>
            <span className="w-14 text-right text-muted">{item.vel}</span>
            <span className={cn(
              "w-12 text-right font-semibold",
              item.sts === "OK" ? "text-ok" :
              item.sts === "LOW" ? "text-warn" : "text-alert"
            )}>{item.sts}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
