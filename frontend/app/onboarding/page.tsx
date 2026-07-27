"use client";

/**
 * Seller onboarding — the context feed from SPEC §12.
 *
 * This exists because a fresh account is an empty room: with no policies, the
 * agent correctly refuses every question, and a dashboard showing zeroes is not
 * a product experience. So the first thing a new seller does is teach it what
 * it is allowed to say.
 *
 * The policy text they paste becomes the passages their agent may cite, and
 * nothing else. Step three proves it by letting them ask.
 */

import { ArrowRight, Check, Plus, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Wordmark } from "@/components/Brand";
import { ChatWidget } from "@/components/ChatWidget";
import {
  Button,
  Card,
  Input,
  Label,
  Textarea,
} from "@/components/ui/primitives";
import { ApiError, api, getAccount, getToken } from "@/lib/api";
import { cn } from "@/lib/utils";

type Draft = { topic: string; body: string };

/** Starters, not defaults: prefilled so nobody faces an empty textarea, and
 * plainly editable so nobody ships our words as their policy. */
const STARTERS: Draft[] = [
  {
    topic: "Refund window",
    body: "Refunds are available within 30 days of delivery, provided the item is unused and in its original packaging. Refunds go back to the original payment method and take 5-10 business days to appear.",
  },
  {
    topic: "Delivery times",
    body: "Standard delivery takes 3-5 working days. Express delivery takes 1-2 working days. Orders placed before 2pm on a working day are dispatched the same day.",
  },
];

const STEPS = ["Your policies", "Try it", "Done"];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = React.useState(0);
  const [drafts, setDrafts] = React.useState<Draft[]>(STARTERS);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState<number>(0);
  const [sessionId] = React.useState(
    () => `onboard-${Math.random().toString(36).slice(2, 9)}`,
  );

  const account = getAccount();
  const usable = drafts.filter((d) => d.topic.trim() && d.body.trim());

  React.useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  function update(i: number, patch: Partial<Draft>) {
    setDrafts((prev) => prev.map((d, n) => (n === i ? { ...d, ...patch } : d)));
  }

  async function savePolicies() {
    if (!usable.length || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.onboardingContext(
        usable.map((d) => ({ topic: d.topic.trim(), body: d.body.trim() })),
      );
      setSaved(result.passages);
      setStep(1);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not save those policies.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-ink">
      <header className="border-b border-line bg-surface/60 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center gap-4 px-5 py-3.5">
          <Wordmark href={null} size={26} />
          <div className="ml-auto flex items-center gap-2">
            {STEPS.map((name, i) => (
              <React.Fragment key={name}>
                {i > 0 && <span className="h-px w-5 bg-line" />}
                <span
                  className={cn(
                    "flex items-center gap-1.5 text-[12px]",
                    i === step
                      ? "text-fg"
                      : i < step
                        ? "text-accent-soft"
                        : "text-faint",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-5 w-5 items-center justify-center rounded-full border text-[10px]",
                      i === step
                        ? "border-accent bg-accent text-white"
                        : i < step
                          ? "border-accent/40 bg-accent/15 text-accent-soft"
                          : "border-line text-faint",
                    )}
                  >
                    {i < step ? <Check size={11} /> : i + 1}
                  </span>
                  <span className="hidden sm:inline">{name}</span>
                </span>
              </React.Fragment>
            ))}
          </div>
        </div>
      </header>

      <main className="flex-1 px-5 py-10">
        <div className="mx-auto max-w-2xl">
          {step === 0 && (
            <>
              <Label className="mb-2">Step one</Label>
              <h1 className="text-title text-fg">
                Teach it what it&apos;s allowed to say
              </h1>
              <p className="mb-7 mt-2.5 text-[14.5px] leading-relaxed text-muted">
                Paste your real policies for{" "}
                <span className="text-body">
                  {account?.business_name ?? "your store"}
                </span>
                . These become the only things it can cite — ask it anything
                outside them and it will say it can&apos;t confirm, rather than
                inventing a rule that sounds plausible.
              </p>

              <div className="flex flex-col gap-3">
                {drafts.map((draft, i) => (
                  <Card key={i} className="p-4">
                    <div className="mb-2.5 flex items-center gap-2">
                      <Input
                        value={draft.topic}
                        onChange={(e) => update(i, { topic: e.target.value })}
                        placeholder="Policy name, e.g. Refund window"
                        className="h-9 flex-1 text-[13px]"
                      />
                      {drafts.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Remove policy"
                          onClick={() =>
                            setDrafts((prev) => prev.filter((_, n) => n !== i))
                          }
                        >
                          <Trash2 size={14} />
                        </Button>
                      )}
                    </div>
                    <Textarea
                      value={draft.body}
                      onChange={(e) => update(i, { body: e.target.value })}
                      rows={4}
                      placeholder="Write it exactly as you would tell a customer."
                      className="text-[13px]"
                    />
                  </Card>
                ))}
              </div>

              <Button
                variant="secondary"
                size="sm"
                className="mt-3"
                onClick={() =>
                  setDrafts((prev) => [...prev, { topic: "", body: "" }])
                }
              >
                <Plus size={14} /> Add another
              </Button>

              {error && (
                <p className="mt-4 rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
                  {error}
                </p>
              )}

              <div className="mt-7 flex items-center gap-3">
                <Button
                  size="lg"
                  onClick={savePolicies}
                  disabled={!usable.length || busy}
                >
                  {busy ? "Teaching it…" : `Save ${usable.length} ${usable.length === 1 ? "policy" : "policies"}`}
                  {!busy && <ArrowRight size={16} />}
                </Button>
                <button
                  onClick={() => router.push("/dashboard")}
                  className="text-[13px] text-faint transition hover:text-body"
                >
                  Skip for now
                </button>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <Label className="mb-2">Step two</Label>
              <h1 className="text-title text-fg">Ask it something</h1>
              <p className="mb-6 mt-2.5 text-[14.5px] leading-relaxed text-muted">
                {saved} {saved === 1 ? "passage is" : "passages are"} loaded. Ask
                about one of them and it will answer with a citation. Ask about
                something you didn&apos;t give it, and watch it decline.
              </p>

              <Card className="h-[26rem] overflow-hidden">
                <ChatWidget
                  sessionId={sessionId}
                  quickReplies={usable.slice(0, 3).map((d) => ({
                    label: d.topic || "Ask",
                    text: `What is your ${d.topic.toLowerCase()}?`,
                  }))}
                />
              </Card>

              <div className="mt-6 flex items-center gap-3">
                <Button size="lg" onClick={() => setStep(2)}>
                  That works <ArrowRight size={16} />
                </Button>
                <button
                  onClick={() => setStep(0)}
                  className="text-[13px] text-faint transition hover:text-body"
                >
                  Edit the policies
                </button>
              </div>
            </>
          )}

          {step === 2 && (
            <div className="pt-6 text-center">
              <span className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-accent/30 bg-accent/12 text-accent">
                <Sparkles size={20} />
              </span>
              <h1 className="text-title text-fg">It&apos;s on shift</h1>
              <p className="mx-auto mb-8 mt-2.5 max-w-md text-[14.5px] leading-relaxed text-muted">
                Your dashboard is next. It will be quiet until real conversations
                start — which is honest, rather than filling it with numbers
                nothing has earned yet.
              </p>
              <div className="flex flex-wrap justify-center gap-3">
                <Button size="lg" onClick={() => router.push("/dashboard")}>
                  Open the dashboard <ArrowRight size={16} />
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  onClick={() => router.push("/integrations")}
                >
                  Put it on my site
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
