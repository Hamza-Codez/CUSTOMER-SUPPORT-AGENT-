"use client";

import { PackageSearch, ScrollText, Boxes, FileText } from "lucide-react";
import * as React from "react";

import { Badge, Card, ErrorState, Skeleton } from "@/components/ui/primitives";
import { ApiError, DEMO_OPERATOR_TOKEN, api } from "@/lib/api";
import type { Overview } from "@/lib/types";

/** Step 9 — records, stock, policies and logs, all live from the backend. */
export function OpsPeek() {
  const [data, setData] = React.useState<Overview | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    api
      .overview(DEMO_OPERATOR_TOKEN)
      .then((d) => !cancelled && setData(d))
      .catch(
        (e) =>
          !cancelled &&
          setError(
            e instanceof ApiError ? e.message : "Could not load the overview.",
          ),
      );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (error)
    return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />;

  if (!data)
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Skeleton className="h-56 rounded-2xl" />
        <Skeleton className="h-56 rounded-2xl" />
      </div>
    );

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Panel icon={<PackageSearch size={14} />} title="Orders">
        {data.orders.slice(0, 5).map((o) => (
          <Row
            key={o.order_id}
            left={o.order_id}
            mid={o.customer_name}
            right={o.total}
            note={o.status.replace("_", " ")}
          />
        ))}
      </Panel>

      <Panel
        icon={<Boxes size={14} />}
        title="Stock"
        meta={
          data.counts.out_of_stock
            ? `${data.counts.out_of_stock} out of stock`
            : undefined
        }
      >
        {data.products.slice(0, 5).map((p) => (
          <Row
            key={p.product_id}
            left={p.name}
            right={p.price}
            note={p.in_stock ? `${p.stock} in stock` : "out of stock"}
            alert={!p.in_stock}
          />
        ))}
      </Panel>

      <Panel icon={<FileText size={14} />} title="Policy documents">
        {data.policies.slice(0, 6).map((p) => (
          <Row key={p.source_ref} left={p.topic} note={p.doc} />
        ))}
      </Panel>

      <Panel icon={<ScrollText size={14} />} title="Audit log">
        {data.recent_activity.slice(0, 6).map((a, i) => (
          <Row
            key={`${a.action}-${i}`}
            left={a.action}
            mid={a.target.slice(0, 22)}
            note={a.outcome}
            alert={
              a.outcome.includes("mismatch") ||
              a.outcome.includes("refused") ||
              a.outcome.includes("blocked")
            }
          />
        ))}
      </Panel>
    </div>
  );
}

function Panel({
  icon,
  title,
  meta,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  meta?: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-center gap-2 border-b border-line-soft px-4 py-2.5">
        <span className="text-accent">{icon}</span>
        <p className="text-[12px] font-medium text-fg">{title}</p>
        {meta && (
          <span className="ml-auto">
            <Badge tone="warn">{meta}</Badge>
          </span>
        )}
      </div>
      <div className="divide-y divide-line-soft">{children}</div>
    </Card>
  );
}

function Row({
  left,
  mid,
  right,
  note,
  alert = false,
}: {
  left: string;
  mid?: string;
  right?: string;
  note?: string;
  alert?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-[12px]">
      <span className="min-w-0 flex-1 truncate text-body">{left}</span>
      {mid && (
        <span className="hidden min-w-0 max-w-[7rem] truncate text-faint sm:block">
          {mid}
        </span>
      )}
      {note && (
        <span className={alert ? "text-alert" : "text-faint"}>{note}</span>
      )}
      {right && <span className="w-14 text-right text-muted">{right}</span>}
    </div>
  );
}
