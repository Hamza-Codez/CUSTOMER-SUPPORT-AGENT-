import * as React from "react";
import { Card, Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function MockOrdersList({ className }: { className?: string }) {
  const orders = [
    { id: "ORD-1005", cx: "Ayesha K", amt: "$150.00", sts: "REV", time: "10m" },
    { id: "ORD-1002", cx: "John D", amt: "$320.00", sts: "DSP", time: "1h" },
    { id: "ORD-0998", cx: "Sarah L", amt: "$89.50", sts: "DEL", time: "1d" },
    { id: "ORD-0995", cx: "Mike T", amt: "$450.00", sts: "PRC", time: "1d" },
    { id: "ORD-0992", cx: "Emma W", amt: "$12.00", sts: "DEL", time: "2d" },
    { id: "ORD-0991", cx: "Chris P", amt: "$95.00", sts: "DSP", time: "2d" },
  ];

  return (
    <Card className={cn("flex flex-col p-0", className)}>
      <div className="flex justify-between items-center p-3 border-b border-line-soft bg-surface/50">
        <h3 className="text-[12px] font-semibold text-fg">Order Book</h3>
      </div>
      <div className="flex flex-col text-[11px] font-mono">
        <div className="flex px-3 py-1.5 text-faint border-b border-line-soft bg-raised/30">
          <span className="w-16">ID</span>
          <span className="flex-1">CUSTOMER</span>
          <span className="w-16 text-right">AMT</span>
          <span className="w-12 text-right">STS</span>
          <span className="w-10 text-right">T</span>
        </div>
        {orders.map((order, i) => (
          <div key={order.id} className={cn("flex px-3 py-1.5 hover:bg-raised transition-colors cursor-default", i !== orders.length - 1 && "border-b border-line-soft/50")}>
            <span className="w-16 text-muted">{order.id.replace('ORD-', '')}</span>
            <span className="flex-1 text-fg truncate pr-2">{order.cx.toUpperCase()}</span>
            <span className="w-16 text-right text-muted">{order.amt}</span>
            <span className={cn(
              "w-12 text-right font-semibold",
              order.sts === "DEL" ? "text-ok" :
              order.sts === "REV" ? "text-warn" :
              order.sts === "DSP" ? "text-accent" : "text-faint"
            )}>{order.sts}</span>
            <span className="w-10 text-right text-faint">{order.time}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
