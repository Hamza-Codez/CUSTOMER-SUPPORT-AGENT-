import * as React from "react";
import { Card, Button, Input } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { SlidersHorizontal, ShieldAlert, Database, Search } from "lucide-react";

export function MockAdminControls({ className }: { className?: string }) {
  const [override, setOverride] = React.useState(false);
  const [tier, setTier] = React.useState<"full" | "product">("full");

  return (
    <Card className={cn("flex flex-col p-0", className)}>
      <div className="flex items-center gap-2 p-3 border-b border-line-soft bg-surface/50">
        <ShieldAlert size={14} className="text-accent" />
        <h3 className="text-[12px] font-semibold text-fg">Admin Console</h3>
      </div>

      <div className="flex flex-col text-[11px]">
        {/* Manual Override Toggle */}
        <div className="flex justify-between items-center p-3 border-b border-line-soft/50 hover:bg-raised/30 transition-colors">
          <div className="flex flex-col">
            <span className="font-mono text-fg uppercase tracking-wider">Manual Override</span>
            <span className="text-[10px] text-faint">Take over customer chat</span>
          </div>
          <button 
            onClick={() => setOverride(!override)}
            className={cn(
              "w-8 h-4 rounded-full relative transition-colors border border-line",
              override ? "bg-accent/80 border-accent" : "bg-raised"
            )}
          >
            <div className={cn(
              "absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-fg transition-transform",
              override ? "translate-x-4 bg-white" : ""
            )} />
          </button>
        </div>

        {/* Answer Tier Selector */}
        <div className="flex flex-col gap-2 p-3 border-b border-line-soft/50 hover:bg-raised/30 transition-colors">
          <span className="font-mono text-fg uppercase tracking-wider">Answer Tier Restrictions</span>
          <div className="grid grid-cols-2 gap-1.5 mt-1">
            <button
              onClick={() => setTier("full")}
              className={cn(
                "py-1 px-2 rounded-sm text-[10px] font-mono border transition-colors",
                tier === "full" ? "border-accent text-accent bg-accent/10" : "border-line text-muted hover:border-line-lit bg-raised/50"
              )}
            >
              [ FULL_ACCESS ]
            </button>
            <button
              onClick={() => setTier("product")}
              className={cn(
                "py-1 px-2 rounded-sm text-[10px] font-mono border transition-colors",
                tier === "product" ? "border-warn text-warn bg-warn/10" : "border-line text-muted hover:border-line-lit bg-raised/50"
              )}
            >
              [ PROD_ONLY ]
            </button>
          </div>
        </div>

        {/* Inventory Query Chat Section */}
        <div className="flex flex-col gap-1.5 p-3 hover:bg-raised/30 transition-colors">
          <div className="flex items-center gap-1.5 mb-1">
            <Database size={12} className="text-muted" />
            <span className="font-mono text-fg uppercase tracking-wider">Direct DB Query</span>
          </div>
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
            <Input 
              placeholder="SELECT stock FROM inventory..." 
              className="pl-7 h-7 text-[10px] font-mono rounded-sm border-line-soft bg-ink" 
            />
          </div>
        </div>
      </div>
    </Card>
  );
}
