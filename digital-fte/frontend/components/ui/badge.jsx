import { cn } from "@/lib/utils";

// Priority is semantic, not decorative — the token names match the data values.
const tones = {
  high: "bg-high-bg text-high-fg border-high-line",
  normal: "bg-normal-bg text-normal-fg border-normal-line",
  low: "bg-low-bg text-low-fg border-low-line",
  accent: "bg-accent-soft text-accent-400 border-accent-700/50",
};

export function Badge({ tone = "low", className, ...props }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        tones[tone] || tones.low,
        className
      )}
      {...props}
    />
  );
}
