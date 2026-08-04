"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { AuthAside, AuthShell } from "@/components/AuthShell";
import { Button, Input } from "@/components/ui/primitives";
import { ApiError, api, signIn } from "@/lib/api";
import { brand } from "@/lib/brand";

const MIN_PASSWORD = 10;

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = React.useState({
    username: "",
    email: "",
    password: "",
  });
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const shortPassword =
    form.password.length > 0 && form.password.length < MIN_PASSWORD;
  const ready =
    form.username.trim() &&
    form.email.trim() &&
    form.password.length >= MIN_PASSWORD;

  function set(field: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.signup(form);
      signIn(result.token, result.account.role, result.account);
      // Straight into onboarding: a new store has no policies and no orders, so
      // the dashboard would be an empty room.
      router.push("/onboarding");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create that account.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Hire your first digital employee"
      subtitle={`Create a ${brand.name} account for your store. It takes a minute, and the demo data is already waiting.`}
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="text-accent-soft hover:underline">
            Sign in
          </Link>
        </>
      }
      aside={
        <AuthAside
          heading="What you get immediately"
          points={[
            {
              title: "Your own store, isolated",
              body: "Sign-up creates a tenant. Nothing you do is visible to any other account, and nothing theirs is visible to you.",
            },
            {
              title: "An operator queue",
              body: "Every decision that moves money arrives prepared, with the reason it stopped and one click to settle it.",
            },
            {
              title: "Analytics that admit ignorance",
              body: "Deflection, approval rate and CSAT from real records — and a blank where there is not enough data yet.",
            },
          ]}
        />
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-3.5">
        <Field label="Username">
          <Input
            value={form.username}
            onChange={(e) => set("username", e.target.value)}
            placeholder="johndoe"
            autoComplete="username"
            autoFocus
          />
        </Field>

        <Field label="Work email">
          <Input
            type="email"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            placeholder="you@yourstore.com"
            autoComplete="email"
          />
        </Field>

        <Field
          label="Password"
          hint={
            shortPassword
              ? `${MIN_PASSWORD - form.password.length} more characters`
              : "At least 10 characters. Length beats punctuation."
          }
          hintTone={shortPassword ? "warn" : "faint"}
        >
          <Input
            type="password"
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
            placeholder="A memorable passphrase"
            autoComplete="new-password"
          />
        </Field>

        {error && (
          <p className="rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" disabled={!ready || busy} className="mt-1">
          {busy ? "Creating your store…" : "Create account"}
          {!busy && <ArrowRight size={16} />}
        </Button>
      </form>
    </AuthShell>
  );
}

function Field({
  label,
  hint,
  hintTone = "faint",
  children,
}: {
  label: string;
  hint?: string;
  hintTone?: "faint" | "warn";
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12.5px] font-medium text-body">{label}</span>
      {children}
      {hint && (
        <span
          className={`text-[11.5px] ${hintTone === "warn" ? "text-warn" : "text-faint"}`}
        >
          {hint}
        </span>
      )}
    </label>
  );
}
