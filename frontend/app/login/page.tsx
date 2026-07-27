"use client";

/**
 * The gateway into the demo.
 *
 * This is honestly a *token* screen, not a sign-up screen. The backend has no
 * /auth/signup or /auth/login yet — it authenticates with the static
 * DEV_TOKENS from its .env — so building a password form here would be a form
 * that posts nowhere. The two buttons below are the two roles those tokens
 * carry, and the field accepts any token the backend is configured with.
 */

import { ArrowRight, Headphones, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button, Card, Input } from "@/components/ui/primitives";
import { signIn } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = React.useState("");

  function enter(value: string, role: string) {
    if (!value.trim()) return;
    signIn(value.trim(), role);
    router.push("/dashboard");
  }

  return (
    <main className="surface-gradient flex min-h-dvh items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <Link
          href="/"
          className="mb-8 flex items-center justify-center gap-2 text-fg"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-sm font-bold text-accent">
            F
          </span>
          <span className="font-semibold">Digital FTE</span>
        </Link>

        <Card accent>
          <div className="p-6">
            <h1 className="mb-1 text-lg font-semibold text-fg">
              Enter the demo
            </h1>
            <p className="mb-6 text-[13px] leading-relaxed text-faint">
              Pick a role to explore both sides of the conversation. Everything
              runs against the seeded demo store.
            </p>

            <div className="mb-5 grid gap-2">
              <RoleButton
                icon={<Headphones size={15} />}
                title="Customer"
                hint="Chat, track an order, ask for a refund"
                onClick={() => enter("demo-token", "customer")}
              />
              <RoleButton
                icon={<SlidersHorizontal size={15} />}
                title="Operator"
                hint="Approve decisions the FTE prepared"
                onClick={() => enter("ops-token", "operator")}
              />
            </div>

            <div className="mb-3 flex items-center gap-3">
              <span className="h-px flex-1 bg-line" />
              <span className="text-[11px] uppercase tracking-wider text-faint">
                or a token
              </span>
              <span className="h-px flex-1 bg-line" />
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                enter(token, "customer");
              }}
              className="flex gap-2"
            >
              <Input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste a DEV_TOKENS value"
                aria-label="Access token"
              />
              <Button type="submit" disabled={!token.trim()}>
                <ArrowRight size={15} />
              </Button>
            </form>
          </div>
        </Card>

        <p className="mt-4 text-center text-[12px] leading-relaxed text-faint">
          Demo tokens, not accounts. Real sign-up arrives with the backend&apos;s
          auth routes.
        </p>
      </div>
    </main>
  );
}

function RoleButton({
  icon,
  title,
  hint,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  hint: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex items-center gap-3 rounded-xl border border-line bg-raised px-4 py-3 text-left transition hover:border-accent/50"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/12 text-accent">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-fg">{title}</span>
        <span className="block text-[12px] text-faint">{hint}</span>
      </span>
      <ArrowRight
        size={15}
        className="shrink-0 text-faint transition group-hover:text-accent"
      />
    </button>
  );
}
