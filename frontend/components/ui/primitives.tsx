/**
 * Base primitives.
 *
 * shadcn's *shape* (cva variants merged with `cn`) but written against our own
 * tokens. Generating defaults and overriding them afterwards is how you end up
 * with something that still reads as stock.
 *
 * What was wrong with the first pass, and what changed:
 *   - every button was a flat fill with a rounded corner. The primary now has a
 *     lit top edge and a glow, so it looks pressable rather than painted on.
 *   - cards were a border on flat grey. They use `panel`, whose top edge catches
 *     light the way a raised surface does.
 *   - nothing had a pressed state, so nothing felt like it responded.
 */

import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const button = cva(
  "relative inline-flex items-center justify-center gap-2 font-medium whitespace-nowrap " +
    "transition-[transform,background-color,border-color,box-shadow] duration-150 " +
    "active:translate-y-px disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        // Magenta, lit along the top edge. `action` carries the fill, the
        // highlight and the glow so nothing here repeats a colour literal.
        primary: "action rounded-xl",
        secondary:
          "rounded-xl border border-line bg-raised text-fg shadow-[inset_0_1px_0_0_rgb(255_255_255/0.04)] " +
          "hover:border-line-lit hover:bg-elevated",
        ghost: "rounded-xl text-muted hover:bg-raised hover:text-fg",
        danger:
          "rounded-xl border border-alert/30 bg-alert/10 text-alert hover:bg-alert/15 hover:border-alert/50",
        subtle:
          "rounded-lg border border-line bg-raised/60 text-muted hover:border-accent/40 hover:text-fg",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-[15px]",
        icon: "h-9 w-9",
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
  raised = false,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  /** Draws the purple hairline along the top edge. */
  accent?: boolean;
  raised?: boolean;
}) {
  return (
    <div
      className={cn(
        raised ? "panel-raised" : "panel",
        "overflow-hidden rounded-2xl",
        className,
      )}
      {...props}
    >
      {accent && <div className="h-px hairline" />}
      {children}
    </div>
  );
}

const badge = cva(
  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium leading-none",
  {
    variants: {
      tone: {
        neutral: "border-line bg-raised text-muted",
        accent: "border-accent/30 bg-accent/12 text-accent-soft",
        ok: "border-ok/25 bg-ok/10 text-ok",
        warn: "border-warn/25 bg-warn/10 text-warn",
        alert: "border-alert/25 bg-alert/10 text-alert",
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

/** Uppercase micro-label. Its own component so the tracking is never forgotten. */
export function Label({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-label uppercase text-faint", className)} {...props} />
  );
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border border-line bg-raised px-4 text-sm text-fg",
        "shadow-[inset_0_1px_2px_rgb(0_0_0/0.35)] transition",
        "placeholder:text-faint hover:border-line-lit focus:border-accent/60",
        "disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full resize-none rounded-xl border border-line bg-raised px-4 py-3 text-sm text-fg",
        "shadow-[inset_0_1px_2px_rgb(0_0_0/0.35)] transition",
        "placeholder:text-faint hover:border-line-lit focus:border-accent/60",
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
      className={cn(
        "relative overflow-hidden rounded-lg bg-raised",
        "after:absolute after:inset-0 after:animate-sweep",
        "after:bg-gradient-to-r after:from-transparent after:via-white/[0.04] after:to-transparent",
        className,
      )}
      {...props}
    />
  );
}

/** Every list view needs one, so it is a component rather than a habit. */
export function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-14 text-center">
      {icon && (
        <div className="mb-1 flex h-11 w-11 items-center justify-center rounded-2xl border border-line bg-raised text-faint">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-body">{title}</p>
      {hint && (
        <p className="max-w-xs text-[13px] leading-relaxed text-faint">{hint}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
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
    <div className="flex flex-col items-start gap-3 rounded-xl border border-alert/25 bg-alert/[0.06] p-4">
      <p className="text-[13px] leading-relaxed text-alert">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
