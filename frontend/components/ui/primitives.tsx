/**
 * Base primitives, in the shadcn shape (cva variants + `cn` merging) but written
 * against our tokens rather than generated with default styling and overridden
 * afterwards. Only the ones actually used are here; a component nobody renders
 * is a component nobody maintains.
 */

import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition " +
    "disabled:pointer-events-none disabled:opacity-45 whitespace-nowrap",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-white hover:bg-accent-soft shadow-[0_1px_0_0_rgba(255,255,255,0.08)_inset]",
        secondary: "bg-raised text-fg border border-line hover:border-accent/60",
        ghost: "text-muted hover:text-fg hover:bg-raised",
        danger: "bg-raised text-alert border border-alert/30 hover:bg-alert/10",
        outline:
          "border border-accent/40 text-accent-soft hover:bg-accent/10",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-[15px]",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof button>;

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button className={cn(button({ variant, size }), className)} {...props} />
  );
}

export function Card({
  className,
  accent = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { accent?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-line bg-surface overflow-hidden",
        className,
      )}
      {...props}
    >
      {accent && <div className="h-px hairline" />}
      {props.children}
    </div>
  );
}

const badge = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium leading-none",
  {
    variants: {
      tone: {
        neutral: "bg-raised text-muted border border-line",
        accent: "bg-accent/12 text-accent-soft border border-accent/25",
        ok: "bg-ok/10 text-ok border border-ok/25",
        warn: "bg-warn/10 text-warn border border-warn/25",
        alert: "bg-alert/10 text-alert border border-alert/25",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...props} />;
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border border-line bg-raised px-4 text-sm text-fg",
        "placeholder:text-faint transition focus:border-accent/60",
        "disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

/** Sized to the content it replaces, so nothing jumps when data arrives. */
export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-lg bg-raised", className)}
      {...props}
    />
  );
}

/** Every list view needs one, so it is a component rather than a habit. */
export function EmptyState({
  title,
  hint,
  icon,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      {icon && <div className="mb-1 text-faint">{icon}</div>}
      <p className="text-sm font-medium text-body">{title}</p>
      {hint && <p className="max-w-xs text-[13px] text-faint">{hint}</p>}
    </div>
  );
}

/** Errors say what broke and what to do about it, never just "error". */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-alert/25 bg-alert/5 p-4">
      <p className="text-[13px] leading-relaxed text-alert">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
