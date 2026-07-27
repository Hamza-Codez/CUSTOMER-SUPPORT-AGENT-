"use client";

/**
 * How the agent actually gets onto a seller's store.
 *
 * The first version of this page was a contact form and nothing else, which is
 * the definition of a dead end dressed as a next step. The methods below are the
 * real ones; the form is for the part that genuinely needs a person — connecting
 * live order data, which depends on the platform.
 */

import { ArrowLeft, Check, Code2, Plug, Send, Webhook } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import {
  Button,
  Card,
  Input,
  Label,
  Textarea,
} from "@/components/ui/primitives";
import { API_BASE, ApiError, DEMO_CUSTOMER_TOKEN, api, getToken } from "@/lib/api";
import { brand } from "@/lib/brand";
import { cn } from "@/lib/utils";

const PLATFORMS = ["Shopify", "WooCommerce", "Magento", "Custom", "Other"];
const VOLUMES = ["Under 500", "500 – 2,000", "2,000 – 10,000", "10,000+"];

type Method = "widget" | "api" | "platform";

export default function IntegrationsPage() {
  const [method, setMethod] = React.useState<Method>("widget");

  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <section className="aura border-b border-line px-5 py-16">
          <div className="mx-auto max-w-4xl">
            <Link
              href="/pricing"
              className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted transition hover:text-fg"
            >
              <ArrowLeft size={14} /> Pricing
            </Link>
            <p className="text-label mb-3 uppercase text-accent">Integration</p>
            <h1 className="text-title text-fg sm:text-display">
              Three ways to put it on your store
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
              The widget takes a minute. The API is there when you want the
              conversation inside your own interface. Connecting live order data
              is the part that needs a person.
            </p>
          </div>
        </section>

        <section className="px-5 py-12">
          <div className="mx-auto max-w-4xl">
            <div className="mb-7 flex flex-wrap gap-2">
              {(
                [
                  { id: "widget", label: "Embedded widget", icon: <Code2 size={14} /> },
                  { id: "api", label: "Direct API", icon: <Webhook size={14} /> },
                  { id: "platform", label: "Your platform", icon: <Plug size={14} /> },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setMethod(tab.id)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-[13px] transition",
                    method === tab.id
                      ? "border-accent/40 bg-accent/12 text-accent-soft"
                      : "border-line bg-raised text-muted hover:border-line-lit hover:text-fg",
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            {method === "widget" && <WidgetMethod />}
            {method === "api" && <ApiMethod />}
            {method === "platform" && <PlatformMethod />}
          </div>
        </section>

        <section className="border-t border-line bg-surface/30 px-5 py-14">
          <div className="mx-auto max-w-xl">
            <h2 className="text-heading text-fg">Connect your real orders</h2>
            <p className="mb-7 mt-2.5 text-[14px] leading-relaxed text-muted">
              This is the part a script tag can&apos;t do. Tell us where your
              orders live and we&apos;ll come back with the steps for your setup.
            </p>
            <RequestForm />
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

function WidgetMethod() {
  const snippet = `<!-- ${brand.name} — paste before </body> -->
<script
  src="https://cdn.${brand.domain}/widget.js"
  data-store="YOUR_STORE_KEY"
  data-api="${API_BASE}"
  defer
></script>`;

  return (
    <div className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
      <div>
        <h2 className="mb-2 text-heading text-fg">One script tag</h2>
        <p className="mb-4 text-[13.5px] leading-relaxed text-muted">
          Drop this before the closing <code className="text-accent-soft">&lt;/body&gt;</code>{" "}
          on your storefront. The launcher appears bottom-right and inherits your
          store key, so it only ever reads your data.
        </p>
        <CodeBlock code={snippet} />
        <p className="mt-3 text-[12px] leading-relaxed text-faint">
          Your store key is issued at sign-up and scopes every request to your
          tenant. It is safe in client-side markup: it identifies a store, it does
          not authorise reading anyone&apos;s account.
        </p>
      </div>

      <Card className="p-5">
        <Label className="mb-3">What the customer gets</Label>
        <ul className="flex flex-col gap-3">
          {[
            "A launcher that matches your site's colours",
            "Identity checked before any order detail appears",
            "Refunds settled or escalated according to your policy",
            "A themed summary email with a one-tap rating",
          ].map((item) => (
            <li key={item} className="flex gap-2.5 text-[13px] text-body">
              <Check size={14} className="mt-0.5 shrink-0 text-ok" />
              {item}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function ApiMethod() {
  const snippet = `curl -X POST ${API_BASE}/chat \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer YOUR_TOKEN' \\
  -d '{
    "message": "Where is my order ORD-1002?",
    "session_id": "customer-8f21"
  }'`;

  const response = `{
  "reply": "I can look that up — could you confirm the email on the order?",
  "session_id": "customer-8f21",
  "actions": [
    { "kind": "routed", "label": "Routed to Orders", "ref": "Orders" }
  ]
}`;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div>
        <h2 className="mb-2 text-heading text-fg">Talk to it directly</h2>
        <p className="mb-4 text-[13.5px] leading-relaxed text-muted">
          One endpoint. Send a message and a session id; the session is the
          conversation&apos;s memory, so reuse it for follow-ups.
        </p>
        <CodeBlock code={snippet} language="bash" />
      </div>
      <div>
        <h2 className="mb-2 text-heading text-fg">What comes back</h2>
        <p className="mb-4 text-[13.5px] leading-relaxed text-muted">
          The reply, plus a record of what it actually did.{" "}
          <span className="text-body">actions</span> is not decoration — a tool
          appears there only because it ran, which is what you render to show a
          customer the work.
        </p>
        <CodeBlock code={response} language="json" />
      </div>
    </div>
  );
}

function PlatformMethod() {
  const steps: Record<string, string[]> = {
    Shopify: [
      "Online Store → Themes → Edit code",
      "Open theme.liquid and paste the widget snippet before </body>",
      "Save; the launcher appears on every storefront page",
      "Send us your store domain so order lookups resolve against real orders",
    ],
    WooCommerce: [
      "Appearance → Theme File Editor, or use a snippet plugin",
      "Add the widget snippet to the wp_footer hook",
      "Save and reload any shop page",
      "Send us your site URL so we can connect the orders endpoint",
    ],
    "Custom store": [
      "Paste the widget snippet into your base template before </body>",
      "Or call POST /chat directly and render the reply and actions yourself",
      "Tell us how your orders are exposed — REST, GraphQL or a database read",
    ],
  };

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {Object.entries(steps).map(([platform, list]) => (
        <Card key={platform} className="p-5">
          <h3 className="mb-3 text-[14px] font-semibold text-fg">{platform}</h3>
          <ol className="flex flex-col gap-2.5">
            {list.map((step, i) => (
              <li key={step} className="flex gap-2.5 text-[12.5px] leading-relaxed text-muted">
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-line text-[10px] text-faint">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </Card>
      ))}
    </div>
  );
}

function RequestForm() {
  const [form, setForm] = React.useState({
    contact_name: "",
    contact_email: "",
    website: "",
    platform: "",
    monthly_conversations: "",
    notes: "",
  });
  const [sending, setSending] = React.useState(false);
  const [sent, setSent] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const ready = form.contact_name.trim() && form.contact_email.trim();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || sending) return;
    setSending(true);
    setError(null);
    try {
      // Someone arriving from the marketing site has no session, so the demo
      // token carries it. A signed-in seller uses their own.
      const result = await api.requestIntegration(
        form,
        getToken() ?? DEMO_CUSTOMER_TOKEN,
      );
      setSent(result.request_id);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not send that.",
      );
    } finally {
      setSending(false);
    }
  }

  if (sent)
    return (
      <Card accent className="p-7 text-center">
        <span className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-ok/12 text-ok">
          <Check size={19} />
        </span>
        <h3 className="mb-2 text-[15px] font-semibold text-fg">
          That&apos;s on the queue
        </h3>
        <p className="text-[13px] leading-relaxed text-muted">
          Logged as <span className="text-accent-soft">{sent}</span>. We&apos;ll
          come back with the steps for your platform.
        </p>
      </Card>
    );

  return (
    <Card accent>
      <form onSubmit={submit} className="flex flex-col gap-3.5 p-6">
        <div className="grid gap-3.5 sm:grid-cols-2">
          <Labelled label="Your name" required>
            <Input
              value={form.contact_name}
              onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
              placeholder="Ayesha K."
            />
          </Labelled>
          <Labelled label="Email" required>
            <Input
              type="email"
              value={form.contact_email}
              onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              placeholder="you@yourstore.com"
            />
          </Labelled>
        </div>

        <Labelled label="Store website">
          <Input
            value={form.website}
            onChange={(e) => setForm({ ...form, website: e.target.value })}
            placeholder="https://yourstore.com"
          />
        </Labelled>

        <Labelled label="Platform">
          <Choices
            options={PLATFORMS}
            value={form.platform}
            onChange={(v) => setForm({ ...form, platform: v })}
          />
        </Labelled>

        <Labelled label="Conversations a month">
          <Choices
            options={VOLUMES}
            value={form.monthly_conversations}
            onChange={(v) => setForm({ ...form, monthly_conversations: v })}
          />
        </Labelled>

        <Labelled label="Anything else">
          <Textarea
            rows={3}
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Where your orders live, what it should handle first…"
          />
        </Labelled>

        {error && (
          <p className="rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" disabled={!ready || sending}>
          {sending ? "Sending…" : "Request integration"}
          {!sending && <Send size={15} />}
        </Button>
      </form>
    </Card>
  );
}

function Labelled({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12.5px] font-medium text-body">
        {label}
        {required && <span className="ml-1 text-accent">*</span>}
      </span>
      {children}
    </label>
  );
}

function Choices({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          onClick={() => onChange(value === option ? "" : option)}
          className={cn(
            "rounded-lg border px-3 py-1.5 text-[12px] transition",
            value === option
              ? "border-accent bg-accent/15 text-accent-soft"
              : "border-line bg-raised text-muted hover:border-accent/40 hover:text-fg",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
