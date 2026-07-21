import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-all disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary: "bg-accent-600 text-white shadow-lift hover:bg-accent-500 active:translate-y-px",
        ghost: "text-ink-muted hover:bg-base-700 hover:text-ink",
        outline: "border border-base-line bg-base-800 text-ink hover:border-accent-600 hover:text-accent-400",
      },
      size: { sm: "h-8 px-3", md: "h-11 px-5", icon: "h-11 w-11" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export function Button({ className, variant, size, ...props }) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
