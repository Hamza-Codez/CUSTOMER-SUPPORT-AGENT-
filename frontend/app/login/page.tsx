"use client";

import { ArrowRight, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { AuthAside, AuthShell } from "@/components/AuthShell";
import { Button, Input } from "@/components/ui/primitives";
import { ApiError, api, signIn } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = React.useState({ email: "", password: "" });
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const ready = form.email.trim() && form.password;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.login(form);
      signIn(result.token, result.account.role, result.account);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not sign you in.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your operator dashboard."
      footer={
        <>
          No account yet?{" "}
          <Link href="/signup" className="text-accent-soft hover:underline">
            Create one
          </Link>
        </>
      }
      aside={
        <AuthAside
          heading="Waiting for you inside"
          points={[
            {
              title: "The escalation queue",
              body: "Refunds the agent prepared but would not make alone, each with the reason it stopped.",
            },
            {
              title: "Your store's own records",
              body: "Orders, stock, policy documents, and every sensitive thing the agent did — including the refusals.",
            },
          ]}
        />
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-3.5">
        <label className="flex flex-col gap-1.5">
          <span className="text-[12.5px] font-medium text-body">Email</span>
          <Input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="you@yourstore.com"
            autoComplete="email"
            autoFocus
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12.5px] font-medium text-body">Password</span>
          <Input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Your passphrase"
            autoComplete="current-password"
          />
        </label>

        {error && (
          <p className="rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" disabled={!ready || busy} className="mt-1">
          {busy ? "Signing in…" : "Sign in"}
          {!busy && <ArrowRight size={16} />}
        </Button>
      </form>

      <div className="mt-6 flex items-center gap-3">
        <span className="h-px flex-1 bg-line" />
        <span className="text-label uppercase text-faint">or</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      {/* The seeded playground needs no account, and saying so is more useful
          than making someone sign up to find out whether it is any good. */}
      <Link
        href="/demo"
        className="mt-4 flex items-center gap-3 rounded-xl border border-line bg-raised px-4 py-3 transition hover:border-accent/45"
      >
        <PlayCircle size={17} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-medium text-fg">
            Explore the demo instead
          </span>
          <span className="block text-[12px] text-faint">
            A seeded store, both sides of the conversation, no sign-up
          </span>
        </span>
        <ArrowRight size={14} className="shrink-0 text-faint" />
      </Link>
    </AuthShell>
  );
}
