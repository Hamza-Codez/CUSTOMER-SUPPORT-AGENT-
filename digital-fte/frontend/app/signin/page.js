"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Headset, User } from "lucide-react";

import {
  isMockAuth, signInAsDemo, signInWithPassword, signUpWithPassword,
} from "../auth";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function SignInPage() {
  const router = useRouter();
  const [error, setError] = useState(null);

  function enter(role) {
    signInAsDemo(role);
    router.replace(role === "agent" ? "/tickets" : "/");
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 pt-10">
      <div className="text-center">
        <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Every action the agent takes is recorded against an account.
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-xl border border-high-line bg-high-bg px-3 py-2 text-sm text-high-fg"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {error}
        </p>
      )}

      {isMockAuth ? (
        <Card>
          <CardBody className="space-y-3">
            <p className="text-sm text-ink-muted">
              Demo mode — no account needed. Pick a role to see what each one can do.
            </p>
            <Button className="w-full" onClick={() => enter("customer")}>
              <User className="h-4 w-4" aria-hidden />
              Continue as a customer
            </Button>
            <Button variant="outline" className="w-full" onClick={() => enter("agent")}>
              <Headset className="h-4 w-4" aria-hidden />
              Continue as a support agent
            </Button>
            <p className="pt-1 text-xs text-ink-faint">
              A customer chats with the agent. Only a support agent can open the
              ticket dashboard — try the other role to see it refused.
            </p>
          </CardBody>
        </Card>
      ) : (
        <PasswordForm onError={setError} onDone={() => router.replace("/")} />
      )}
    </div>
  );
}

function PasswordForm({ onError, onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("signin");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    onError(null);

    const run = mode === "signin" ? signInWithPassword : signUpWithPassword;
    const { error } = await run(email, password);

    setBusy(false);
    if (error) onError(error);
    else onDone();
  }

  return (
    <Card>
      <CardBody>
        <form className="space-y-3" onSubmit={submit}>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            aria-label="Email"
            autoComplete="email"
            required
          />
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            aria-label="Password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            required
          />
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <button
          type="button"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="mt-3 w-full text-xs text-ink-muted underline-offset-2 hover:text-ink hover:underline"
        >
          {mode === "signin"
            ? "No account? Create one"
            : "Already have an account? Sign in"}
        </button>
      </CardBody>
    </Card>
  );
}
