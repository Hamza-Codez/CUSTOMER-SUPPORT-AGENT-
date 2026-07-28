"use client";

/**
 * The console — one window, two lenses.
 *
 * The two lenses are the emotional centre of the product: you watch your
 * employee stop short of a refund from the customer's seat, flip, and find the
 * decision already waiting on your desk. So the switch is a top-level control
 * rather than a tab in a settings page, it says what each side *is* rather than
 * naming two roles, and the choice survives a reload.
 */

import { Headphones, LogOut, SlidersHorizontal, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Wordmark } from "@/components/Brand";
import { ChatWidget } from "@/components/ChatWidget";
import { SellerView } from "@/components/SellerView";
import { ToolRack } from "@/components/ToolRack";
import { Badge, Button } from "@/components/ui/primitives";
import { api, getAccount, getRole, getToken, signOut } from "@/lib/api";
import { toolForKind, type ToolId } from "@/lib/tools";
import type { Account, ChatResponse, Health } from "@/lib/types";
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
  const [used, setUsed] = React.useState<Set<ToolId>>(() => new Set());
  const [sessionId] = React.useState(
    () => `web-${Math.random().toString(36).slice(2, 9)}`,
  );

  // Reading during render is fine — these are plain reads with no side effects,
  // and `mounted` guarantees `window` exists.
  const authed = mounted && Boolean(getToken());
  const role = mounted ? getRole() : null;
  const account: Account | null = mounted ? getAccount() : null;
  const mode: Mode = modeOverride ?? (mounted ? readMode() : "customer");

  React.useEffect(() => {
    // Gate on the client: the token lives in localStorage, which the server
    // cannot see.
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

  /** A tool lights up only because the backend reported it acting. */
  function recordTools(response: ChatResponse) {
    setUsed((prev) => {
      const next = new Set(prev);
      for (const action of response.actions) {
        const tool = toolForKind(action.kind);
        if (tool) next.add(tool.id);
      }
      return next;
    });
  }

  if (!authed) return null;

  return (
    <div className="flex h-dvh flex-col bg-ink">
      <header className="border-b border-line bg-surface/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
          <Wordmark />

          <ModeToggle mode={mode} onChange={switchMode} />

          <div className="ml-auto flex items-center gap-2">
            {account && (
              <span className="hidden text-right lg:block">
                <span className="block text-[12.5px] font-medium text-fg">
                  {account.business_name}
                </span>
                <span className="block text-[11px] text-faint">
                  {account.email}
                </span>
              </span>
            )}
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
          This account is signed in as a customer. The operator queue will refuse
          this token — sign in with an operator account to action anything.
        </div>
      )}

      <main className="flex-1 overflow-hidden">
        {mode === "customer" ? (
          <div className="mx-auto flex h-full max-w-6xl gap-0">
            <div className="min-w-0 flex-1">
              <ChatWidget sessionId={sessionId} onExchange={recordTools} />
            </div>

            {/* The toolbelt, beside the conversation. This is what separates an
                employee from a chat box: you can see what it can reach. */}
            <aside className="hidden w-72 shrink-0 overflow-y-auto border-l border-line bg-surface/40 px-4 py-5 lg:block">
              <ToolRack used={used} />
              <Link
                href="/onboarding"
                className="mt-5 flex items-center gap-2 rounded-xl border border-line bg-raised px-3 py-2.5 text-[12px] text-muted transition hover:border-line-lit hover:text-fg"
              >
                <Sparkles size={13} className="text-accent-soft" />
                Teach it your policies
              </Link>
            </aside>
          </div>
        ) : (
          <div className="h-full overflow-y-auto">
            <SellerView />
          </div>
        )}
      </main>
    </div>
  );
}

/** Two lenses on the same conversation, labelled by what you see rather than by
 * a role name — "Seller" told nobody anything about what the button does. */
function ModeToggle({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  const options: {
    id: Mode;
    label: string;
    hint: string;
    icon: React.ReactNode;
  }[] = [
    {
      id: "customer",
      label: "Storefront",
      hint: "What your customer sees",
      icon: <Headphones size={13} />,
    },
    {
      id: "seller",
      label: "Your desk",
      hint: "Decisions waiting for you",
      icon: <SlidersHorizontal size={13} />,
    },
  ];

  return (
    <div
      role="tablist"
      aria-label="View"
      className="ml-2 flex rounded-xl border border-line bg-raised p-0.5 shadow-[inset_0_1px_2px_rgb(0_0_0/0.3)]"
    >
      {options.map((option) => (
        <button
          key={option.id}
          role="tab"
          title={option.hint}
          aria-selected={mode === option.id}
          onClick={() => onChange(option.id)}
          className={cn(
            // 6px inside an 8px container with 2px padding — concentric, so the
            // gap between the two curves stays even.
            "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition",
            mode === option.id ? "bg-ok/20 text-ok shadow-[inset_0_1px_0_0_rgb(255_255_255/0.1)]" : "text-muted hover:text-fg",
          )}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  );
}
