"use client";

import { Mail } from "lucide-react";
import * as React from "react";

import { Badge, Card, EmptyState, Skeleton } from "@/components/ui/primitives";
import { DEMO_OPERATOR_TOKEN, api } from "@/lib/api";
import type { EmailPreview } from "@/lib/types";

/**
 * Step 8 — the summary email, shown as the customer will receive it.
 *
 * The markup comes back from the backend exactly as it was rendered and stored,
 * so this is the real message rather than a mock-up of one. It is rendered in a
 * sandboxed iframe: it is stored HTML, and the surrounding app should not be
 * reachable from it even though we generated it ourselves.
 */
export function EmailPreviewPanel({ sessionId }: { sessionId: string }) {
  const [email, setEmail] = React.useState<EmailPreview | null>(null);
  const [missing, setMissing] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    api
      .emailPreview(sessionId, DEMO_OPERATOR_TOKEN)
      .then((e) => !cancelled && setEmail(e))
      .catch(() => !cancelled && setMissing(true));
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (missing)
    return (
      <Card>
        <EmptyState
          icon={<Mail size={20} />}
          title="No summary yet"
          hint="Ask the agent to email you a summary and it will appear here."
        />
      </Card>
    );

  if (!email) return <Skeleton className="h-72 w-full rounded-2xl" />;

  return (
    <Card accent>
      <div className="flex flex-wrap items-center gap-2 border-b border-line-soft px-4 py-2.5">
        <Mail size={14} className="text-accent" />
        <p className="min-w-0 flex-1 truncate text-[12px] text-fg">
          {email.subject}
        </p>
        <Badge tone={email.status === "failed" ? "alert" : "ok"}>
          {email.status === "recorded" ? "not actually sent (demo)" : email.status}
        </Badge>
      </div>
      <p className="px-4 pt-2 text-[11px] text-faint">To {email.recipient}</p>
      <iframe
        title="Summary email preview"
        sandbox=""
        srcDoc={email.body_html}
        className="h-80 w-full border-0"
      />
    </Card>
  );
}
