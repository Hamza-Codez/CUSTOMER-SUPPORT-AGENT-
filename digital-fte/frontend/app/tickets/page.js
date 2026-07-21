"use client";
import { useEffect, useState } from "react";
import { AlertTriangle, Inbox, ShieldAlert } from "lucide-react";

import { useRouter } from "next/navigation";

import { AuthError, fetchTickets } from "../api";
import { isSignedIn } from "../auth";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const POLL_MS = 3000;

export default function TicketsPage() {
  const router = useRouter();
  const [tickets, setTickets] = useState(null);   // null = still loading
  const [error, setError] = useState(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    if (!isSignedIn()) {
      router.replace("/signin");
      return;
    }

    let alive = true;
    let timer;      // declared first: load() clears it on a 403

    async function load() {
      try {
        const data = await fetchTickets();
        if (!alive) return;
        setTickets(data.tickets);
        setError(null);
      } catch (e) {
        if (!alive) return;
        if (e instanceof AuthError && e.status === 403) {
          // Authenticated, wrong role. Stop polling — retrying can't fix it.
          setDenied(true);
          setTickets([]);
          alive = false;
          clearInterval(timer);
        } else if (e instanceof AuthError) {
          router.replace("/signin");
        } else {
          setError("Can't reach the backend — is it running on :8000?");
        }
      }
    }

    load();
    timer = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [router]);

  if (denied) {
    return (
      <Card>
        <CardBody className="flex flex-col items-center gap-2 py-12 text-center">
          <ShieldAlert className="h-6 w-6 text-high-fg" aria-hidden />
          <p className="text-sm font-medium">Support agents only</p>
          <p className="max-w-sm text-sm text-ink-muted">
            The audit log contains other customers' order details, so it's
            restricted to the support team. You're signed in as a customer.
          </p>
        </CardBody>
      </Card>
    );
  }

  const escalated = tickets?.filter((t) => t.escalated).length ?? 0;

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Audit log</h1>
          <p className="text-sm text-ink-muted">
            Every action the agent takes lands here. Live, newest first.
          </p>
        </div>
        {tickets?.length > 0 && (
          <div className="flex shrink-0 gap-2">
            <Badge tone="low">{tickets.length} total</Badge>
            {escalated > 0 && <Badge tone="high">{escalated} escalated</Badge>}
          </div>
        )}
      </header>

      {error && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-xl border border-high-line bg-high-bg px-3 py-2 text-sm text-high-fg"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {error}
        </p>
      )}

      {/* Loading: skeletons sized to a real card, so nothing jumps on arrival. */}
      {tickets === null && !error && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardBody className="space-y-3">
                <div className="flex justify-between gap-3">
                  <Skeleton className="h-4 w-52" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <Skeleton className="h-3 w-4/5" />
                <Skeleton className="h-3 w-24" />
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Empty: name the next action rather than just saying "nothing here". */}
      {tickets?.length === 0 && (
        <Card>
          <CardBody className="flex flex-col items-center gap-2 py-12 text-center">
            <Inbox className="h-6 w-6 text-ink-faint" aria-hidden />
            <p className="text-sm font-medium">No tickets yet</p>
            <p className="max-w-xs text-sm text-ink-muted">
              Ask the agent to refund ORD-1002 — the approval will appear here within
              a few seconds.
            </p>
          </CardBody>
        </Card>
      )}

      {tickets?.map((ticket) => (
        <Ticket key={ticket.id} ticket={ticket} />
      ))}
    </div>
  );
}

function Ticket({ ticket }) {
  return (
    <Card className="animate-fade-up transition-colors hover:border-base-600">
      <CardHeader>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-ink-faint">{ticket.id}</span>
            {ticket.order_id && (
              <span className="font-mono text-xs text-accent-400">{ticket.order_id}</span>
            )}
          </div>
          <h2 className="mt-1 truncate text-sm font-semibold">{ticket.subject}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {ticket.escalated && (
            <Badge tone="high">
              <ShieldAlert className="h-3 w-3" aria-hidden />
              Escalated
            </Badge>
          )}
          <Badge tone={ticket.priority === "high" ? "high" : "normal"}>
            {ticket.priority}
          </Badge>
        </div>
      </CardHeader>
      <CardBody className="pt-2">
        <p className="text-sm leading-relaxed text-ink-muted">{ticket.detail}</p>
        <p className="mt-2 font-mono text-[11px] text-ink-faint">
          {ticket.status} · {ticket.created_at}
        </p>
      </CardBody>
    </Card>
  );
}
