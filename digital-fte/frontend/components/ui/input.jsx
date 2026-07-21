import { forwardRef } from "react";
import { cn } from "@/lib/utils";

// forwardRef so callers can return focus to the field after sending.
export const Input = forwardRef(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-11 w-full rounded-xl border border-base-line bg-base-800 px-4 text-sm text-ink",
        "placeholder:text-ink-faint transition-colors hover:border-base-600",
        "focus:border-accent-600 disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
});
