"use client";

import { Check, Copy } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/** A snippet someone is meant to actually take, so copying is the primary action. */
export function CodeBlock({
  code,
  language = "html",
  className,
}: {
  code: string;
  language?: string;
  className?: string;
}) {
  const [copied, setCopied] = React.useState(false);

  React.useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1800);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      // Clipboard is blocked in some embedded contexts; the code is selectable
      // either way, so failing silently is better than an alarming error.
    }
  }

  return (
    <div className={cn("panel overflow-hidden rounded-xl", className)}>
      <div className="flex items-center gap-2 border-b border-line-soft px-3 py-1.5">
        <span className="text-label uppercase text-faint">{language}</span>
        <button
          onClick={copy}
          className={cn(
            "ml-auto inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] transition",
            copied
              ? "bg-ok/[0.08] text-ok"
              : "text-muted hover:bg-raised hover:text-fg"
          )}
        >
          {copied ? <Check size={11} className="text-ok" /> : <Copy size={11} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3.5 text-[12.5px] leading-relaxed">
        <code className="font-mono text-body">{code}</code>
      </pre>
    </div>
  );
}
