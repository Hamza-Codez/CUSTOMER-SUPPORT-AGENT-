"use client";

/**
 * The dual dashboard — one window, two lenses.
 *
 * The customer/seller toggle is the emotional centre of the product: you watch
 * the FTE stop short of a refund, flip, and see the decision waiting for you.
 * So it is a top-level control, not a tab buried in a settings page, and the
 * mode persists across reloads.
 */

import { Headphones, LogOut, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { ChatWidget } from "@/components/ChatWidget";
import { SellerView } from "@/components/SellerView";
import { Badge, Button } from "@/components/ui/primitives";
import { api, getRole, getToken, signOut } from "@/lib/api";
import type { Health } from "@/lib/types";
import { cn } from "@/lib/utils";

type Mode = "customer" | "seller";

/** True only on the client, without a state update.
 *
 * The page is prerendered, so anything read from localStorage differs between
 * the server and the first client render. Deriving "are we mounted yet" from an
 * external store rather than an effect avoids both the hydration mismatch and
 * the extra render an effect-plus-setState would cause. */
const NEVER_CHANGES = () => () => {};

function useMounted() {
  return React.useSyncExternalStore(
    NEVER_CHANGES,
    () => true,
    () => false,
  );
}

function readMode(): Mode {
  const saved = window.localStorage.getItem("fte.mode");
  return saved === "seller" ? "seller" : "customer";
}

export default function DashboardPage() {
  const router = useRouter();
  const mounted = useMounted();
  const [modeOverride, setModeOverride] = React.useState<Mode | null>(null);
  const [health, setHealth] = React.useState<Health | null>(null);
  const [sessionId] = React.useState(
    () => `web-${Math.random().toString(36).slice(2, 9)}`,
  );

  // Reading during render is fine — these are plain reads with no side effects,
  // and `mounted` guarantees `window` exists.
  const authed = mounted && Boolean(getToken());
  const role = mounted ? getRole() : null;
  const mode: Mode = modeOverride ?? (mounted ? readMode() : "customer");

  React.useEffect(() => {
    // Gate on the client: the token lives in localStorage, which the server
    // cannot see. Real cookie-based auth arrives with the backend's /auth routes.
    if (mounted && !getToken()) router.replace("/login");
  }, [mounted, router]);

  React.useEffect(() => {
    if (!authed) return;
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => !cancelled && setHealth(null));
    return () => {
      cancelled = true;
    };
  }, [authed]);

  function switchMode(next: Mode) {
    setModeOverride(next);
    window.localStorage.setItem("fte.mode", next);
  }

  if (!authed) return null;

  return (
    <div className="flex h-dvh flex-col bg-ink">
      <header className="border-b border-line bg-surface/70 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15 text-[13px] font-bold text-accent">
              F
            </span>
            <span className="hidden text-sm font-semibold text-fg sm:inline">
              Digital FTE
            </span>
          </Link>

          <ModeToggle mode={mode} onChange={switchMode} />

          <div className="ml-auto flex items-center gap-2">
            {health && (
              <Badge tone={health.db === "up" ? "neutral" : "alert"}>
                {health.provider} · {health.store}
              </Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                signOut();
                router.replace("/login");
              }}
              aria-label="Sign out"
            >
              <LogOut size={14} />
            </Button>
          </div>
        </div>
      </header>

      {mode === "seller" && role !== "operator" && (
        <div className="border-b border-warn/25 bg-warn/5 px-4 py-2 text-center text-[12px] text-warn sm:px-6">
          You are signed in as a customer. The operator queue will refuse this
          token — sign in with the operator one to action anything.
        </div>
      )}

      <main className="flex-1 overflow-hidden">
        {mode === "customer" ? (
          <ChatWidget sessionId={sessionId} />
        ) : (
          <div className="h-full overflow-y-auto">
            <SellerView />
          </div>
        )}
      </main>
    </div>
  );
}

function ModeToggle({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  const options: { id: Mode; label: string; icon: React.ReactNode }[] = [
    { id: "customer", label: "Customer", icon: <Headphones size={13} /> },
    { id: "seller", label: "Seller", icon: <SlidersHorizontal size={13} /> },
  ];

  return (
    <div
      role="tablist"
      aria-label="View mode"
      className="ml-2 flex rounded-xl border border-line bg-raised p-0.5"
    >
      {options.map((option) => (
        <button
          key={option.id}
          role="tab"
          aria-selected={mode === option.id}
          onClick={() => onChange(option.id)}
          className={cn(
            "flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-[12px] font-medium transition",
            mode === option.id
              ? "bg-accent text-white"
              : "text-muted hover:text-fg",
          )}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  );
}
