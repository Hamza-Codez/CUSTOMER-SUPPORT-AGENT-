"use client";

import { ArrowRight, Check, Globe } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Wordmark } from "@/components/Brand";
import {
  Button,
  Card,
  Input,
  Label,
  Textarea,
} from "@/components/ui/primitives";
import { ApiError, api, getAccount, getToken, signIn } from "@/lib/api";
import type { SiteScanResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS = ["Contact Info", "Policies", "Brand Voice"];

/** The signed-in account's suggested store name, read hydration-safely.
 *
 * localStorage differs between the server render and the first client one, so
 * this comes from an external store rather than an effect. The account is
 * written once at sign-in and does not change while this page is open, hence
 * the no-op subscribe. */
const NEVER_CHANGES = () => () => {};

function useSuggestedStoreName(): string {
  return React.useSyncExternalStore(
    NEVER_CHANGES,
    () => {
      const account = getAccount();
      return account ? `${account.username}'s Store` : "";
    },
    () => "",
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = React.useState(0);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  
  const [form, setForm] = React.useState({
    store_name: "",
    store_url: "",
    whatsapp: "",
    policies_text: "",
    brand_voice: "",
  });

  React.useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  // The suggested store name is *derived*, not written into state by an effect.
  // Seeding state from localStorage in an effect meant a cascading render, and
  // seeding it in useState would differ between the server render and the first
  // client one. Reading it from an external store is correct on both counts, and
  // an empty field simply falls back to the suggestion until the seller types.
  const suggested = useSuggestedStoreName();
  const storeName = form.store_name || suggested;

  function set(field: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const step1Ready = storeName.trim() && form.store_url.trim() && form.whatsapp.trim();
  const step2Ready = form.policies_text.trim();
  const step3Ready = form.brand_voice.trim();

  async function completeProfile() {
    if (!step1Ready || !step2Ready || !step3Ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.completeProfile({ ...form, store_name: storeName });
      signIn(getToken()!, result.role, result); // update account context
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not complete profile.",
      );
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
                        ? "border-magenta bg-magenta text-white"
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
            <div className="flex flex-col gap-5 animate-in fade-in slide-in-from-bottom-2">
              <div>
                <Label className="mb-2">Step one</Label>
                <h1 className="text-title text-fg">
                  Let&apos;s set up your store
                </h1>
                <p className="mt-2.5 text-[14.5px] leading-relaxed text-muted">
                  Provide your core business details so the agent knows who it is working for and how to handle contact inquiries.
                </p>
              </div>

              <Card className="p-5 flex flex-col gap-4">
                <Field label="Store Name">
                  <Input 
                    value={storeName}
                    onChange={(e) => set("store_name", e.target.value)} 
                    placeholder="e.g. Aeron Home Goods"
                  />
                </Field>

                <Field label="Store Website URL">
                  <Input 
                    value={form.store_url} 
                    onChange={(e) => set("store_url", e.target.value)} 
                    placeholder="https://yourstore.com"
                  />
                </Field>

                <Field label="WhatsApp Support Number">
                  <Input 
                    value={form.whatsapp} 
                    onChange={(e) => set("whatsapp", e.target.value)} 
                    placeholder="+1234567890"
                  />
                </Field>
              </Card>

              <div className="mt-2 flex items-center gap-3">
                <Button size="lg" disabled={!step1Ready} onClick={() => setStep(1)}>
                  Next <ArrowRight size={16} />
                </Button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="flex flex-col gap-5 animate-in fade-in slide-in-from-bottom-2">
              <div>
                <Label className="mb-2">Step two</Label>
                <h1 className="text-title text-fg">Knowledge Base</h1>
                <p className="mt-2.5 text-[14.5px] leading-relaxed text-muted">
                  Paste your policies below. This is what the agent will read when answering customer queries.
                </p>
              </div>
              
              <SiteScanPanel 
                onImport={(text) => {
                  set("policies_text", (form.policies_text + "\n\n" + text).trim());
                }} 
              />

              <Card className="p-4 flex flex-col gap-3">
                <Label className="text-fg">Policies</Label>
                <Textarea 
                  rows={10} 
                  value={form.policies_text} 
                  onChange={(e) => set("policies_text", e.target.value)} 
                  placeholder="Paste your refund policy, delivery times, and FAQs here..."
                />
              </Card>

              <div className="mt-2 flex items-center gap-3">
                <Button variant="secondary" onClick={() => setStep(0)}>Back</Button>
                <Button size="lg" disabled={!step2Ready} onClick={() => setStep(2)}>
                  Next <ArrowRight size={16} />
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-5 animate-in fade-in slide-in-from-bottom-2">
              <div>
                <Label className="mb-2">Step three</Label>
                <h1 className="text-title text-fg">Brand Voice</h1>
                <p className="mt-2.5 text-[14.5px] leading-relaxed text-muted">
                  How should your agent sound? Write a short instruction on the tone of voice.
                </p>
              </div>

              <Card className="p-5 flex flex-col gap-4">
                <Label className="text-fg">Voice Instructions</Label>
                <Textarea 
                  rows={4} 
                  value={form.brand_voice} 
                  onChange={(e) => set("brand_voice", e.target.value)} 
                  placeholder="e.g. Professional, courteous, but concise. Use emojis sparingly. Say 'we' instead of 'I'."
                />
              </Card>

              {error && (
                <p className="rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
                  {error}
                </p>
              )}

              <div className="mt-2 flex items-center gap-3">
                <Button variant="secondary" onClick={() => setStep(1)} disabled={busy}>Back</Button>
                <Button size="lg" disabled={!step3Ready || busy} onClick={completeProfile}>
                  {busy ? "Finishing..." : "Complete Setup"} {!busy && <Check size={16} />}
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12.5px] font-medium text-body">{label}</span>
      {children}
    </label>
  );
}

function SiteScanPanel({ onImport }: { onImport: (text: string) => void }) {
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<SiteScanResult | null>(null);
  const [chosen, setChosen] = React.useState<Set<string>>(() => new Set());
  const [error, setError] = React.useState<string | null>(null);

  async function scan(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const body = await api.scanSite(url.trim());
      setResult(body);
      setChosen(new Set(body.pages.map((p) => p.url)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't read that site.");
    } finally {
      setBusy(false);
    }
  }

  function importChosen() {
    if (!result) return;
    const combined = result.pages
      .filter((p) => chosen.has(p.url))
      .map((p) => `## ${p.topic}\n${p.text}`)
      .join("\n\n");
    onImport(combined);
    setResult(null);
    setUrl("");
  }

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center gap-2">
        <Globe size={15} className="text-accent-soft" />
        <p className="text-[14px] font-medium text-fg">
          Have existing policies online?
        </p>
      </div>
      <p className="mb-4 text-[12.5px] leading-relaxed text-muted">
        We can scan your site to pre-fill the text area below.
      </p>

      <form onSubmit={scan} className="flex flex-wrap gap-2">
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://yourstore.com"
          className="min-w-48 flex-1 h-9"
        />
        <Button type="submit" variant="secondary" size="sm" disabled={busy || !url.trim()} className="h-9">
          {busy ? "Scanning…" : "Scan Site"}
        </Button>
      </form>

      {error && <p className="mt-3 text-[12.5px] text-alert">{error}</p>}

      {result && (
        <div className="mt-4 flex flex-col gap-2">
          {result.pages.map((page) => {
            const on = chosen.has(page.url);
            return (
              <label
                key={page.url}
                className={cn(
                  "flex cursor-pointer gap-3 rounded-xl border p-3 transition",
                  on
                    ? "border-accent/35 bg-accent/[0.06]"
                    : "border-line hover:border-line-lit",
                )}
              >
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() =>
                    setChosen((prev) => {
                      const next = new Set(prev);
                      if (on) next.delete(page.url);
                      else next.add(page.url);
                      return next;
                    })
                  }
                  className="mt-1 h-3.5 w-3.5 shrink-0 accent-current"
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-fg">
                    {page.topic}
                  </span>
                  <span className="mt-1.5 line-clamp-3 text-[12px] text-muted">
                    {page.text}
                  </span>
                </span>
              </label>
            );
          })}
          {result.pages.length > 0 && (
            <Button
              className="mt-1 self-start"
              size="sm"
              onClick={importChosen}
              disabled={chosen.size === 0}
            >
              Import Selected
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
