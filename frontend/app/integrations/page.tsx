"use client";

/**
 * How the agent actually gets onto a seller's store.
 *
 * The first version of this page was a contact form and nothing else, which is
 * the definition of a dead end dressed as a next step. The methods below are the
 * real ones; the form is for the part that genuinely needs a person — connecting
 * live order data, which depends on the platform.
 */

import { ArrowLeft, Check, Code2, Plug, Send, Wand2, Webhook } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import * as React from "react";

import integrationsImg from "../../public/assets/integrations.png";

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
import type { SiteKey } from "@/lib/types";
import { cn } from "@/lib/utils";

const PLATFORMS = ["Shopify", "WooCommerce", "Magento", "Custom", "Other"];
const VOLUMES = ["Under 500", "500 – 2,000", "2,000 – 10,000", "10,000+"];

type Method = "widget" | "preview" | "api" | "platform";

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
              Four ways to put it on your store
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
              The widget takes a minute, and you can see it running on your own
              storefront before you change a line of it. The API is there when you
              want the conversation inside your own interface. Connecting live
              order data is the part that needs a person.
            </p>
          </div>
        </section>

        <section className="px-5 py-12">
          <div className="mx-auto max-w-4xl">
            <div className="mb-7 flex flex-wrap gap-2">
              {(
                [
                  { id: "widget", label: "Embedded widget", icon: <Code2 size={14} /> },
                  { id: "preview", label: "Try it on your site", icon: <Wand2 size={14} /> },
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
                      ? "border-ok/40 bg-ok/12 text-ok"
                      : "border-line bg-raised text-muted hover:border-line-lit hover:text-fg",
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            {method === "widget" && <WidgetMethod />}
            {method === "preview" && <PreviewMethod />}
            {method === "api" && <ApiMethod />}
            {method === "platform" && <PlatformMethod />}
          </div>
        </section>

        <section className="border-t border-line bg-surface/30 px-5 py-14">
          <div className="mx-auto max-w-5xl">
            <div className="grid gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-center">
              <div>
                <h2 className="text-heading text-fg">Connect your real orders</h2>
                <p className="mb-7 mt-2.5 text-[14px] leading-relaxed text-muted">
                  This is the part a script tag can&apos;t do. Tell us where your
                  orders live and we&apos;ll come back with the steps for your setup.
                </p>
                <RequestForm />
              </div>
              <div className="flex items-center justify-center lg:justify-end">
                <Image
                  src={integrationsImg}
                  alt="Integrations"
                  className="w-full max-w-56 object-contain lg:max-w-80"
                />
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

/** Mints a real key and shows the real snippet.
 *
 * The previous version of this printed a script tag pointing at a CDN that did
 * not exist, with a placeholder key nobody could obtain — a screenshot of an
 * integration. Everything below comes back from the API: the key, the origins it
 * is locked to, and the exact line to paste, assembled server-side so a copied
 * snippet cannot disagree with itself.
 */
function WidgetMethod() {
  const [keys, setKeys] = React.useState<SiteKey[] | null>(null);
  const [origin, setOrigin] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const signedIn = useSignedIn();

  // Bumped after a mint or a revoke to re-run the fetch below. A counter rather
  // than calling the loader directly: the fetch lives entirely inside the effect
  // so its result can be discarded if the component unmounts mid-flight.
  const [reload, setReload] = React.useState(0);

  React.useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    api
      .siteKeys()
      .then((body) => !cancelled && setKeys(body.keys))
      .catch(
        (e) =>
          !cancelled &&
          setError(e instanceof ApiError ? e.message : "Couldn't load your keys."),
      );
    return () => {
      cancelled = true;
    };
  }, [signedIn, reload]);

  async function mint(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createSiteKey({
        label: origin.trim() || "Storefront",
        allowed_origins: [origin.trim()],
      });
      setOrigin("");
      setReload((n) => n + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't create that key.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(key: string) {
    setError(null);
    try {
      await api.revokeSiteKey(key);
      setReload((n) => n + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't revoke that key.");
    }
  }

  const live = (keys ?? []).filter((k) => k.active && !k.preview);

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="min-w-0">
        <h2 className="mb-2 text-heading text-fg">One script tag</h2>
        <p className="mb-4 text-[13.5px] leading-relaxed text-muted">
          Paste it before the closing{" "}
          <code className="text-accent-soft">&lt;/body&gt;</code> on your
          storefront. The launcher appears bottom-right, in a shadow root, so it
          can neither inherit your CSS nor leak its own.
        </p>

        {!signedIn ? (
          <Card className="p-5">
            <p className="text-[13.5px] text-body">
              Keys belong to an account, so this needs you signed in.
            </p>
            <div className="mt-4 flex gap-2">
              <Link
                href="/signup"
                className="action inline-flex h-10 items-center rounded-xl px-4 text-[13px] font-medium"
              >
                Create an account
              </Link>
              <Link
                href="/login"
                className="inline-flex h-10 items-center rounded-xl border border-line bg-raised px-4 text-[13px] text-body transition hover:border-line-lit"
              >
                Sign in
              </Link>
            </div>
          </Card>
        ) : (
          <>
            {live.length > 0 ? (
              <div className="flex min-w-0 flex-col gap-4">
                {/* Labelled, because an existing key appearing the moment the
                    page loads otherwise reads as one having just been minted. */}
                <Label>
                  {live.length === 1 ? "Your key" : `Your keys (${live.length})`}
                </Label>
                {live.map((key) => (
                  <div key={key.key} className="min-w-0">
                    <CodeBlock code={key.snippet} />
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-faint">
                      <span className="min-w-0 break-all">
                        Locked to {key.allowed_origins.join(", ") || "no origin"}
                      </span>
                      <button
                        onClick={() => revoke(key.key)}
                        className="ml-auto shrink-0 text-alert transition hover:underline"
                      >
                        Revoke
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-muted">
                No keys yet. Add the domain your storefront runs on:
              </p>
            )}

            <form onSubmit={mint} className="mt-4 flex flex-wrap gap-2">
              <Input
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                placeholder="https://yourstore.com"
                aria-label="Storefront domain"
                className="min-w-48 flex-1"
              />
              <Button type="submit" disabled={busy || !origin.trim()}>
                {busy ? "Creating…" : "Create key"}
              </Button>
            </form>
            {error && <p className="mt-2 text-[12px] text-alert">{error}</p>}
          </>
        )}

        <p className="mt-4 text-[12px] leading-relaxed text-faint">
          The key is public and meant to be readable in your page source. It
          identifies your store and authorises exactly one endpoint — starting a
          customer conversation. It cannot read your operator queue, approve a
          refund, or reach another business, and it only works from the domains
          listed above.
        </p>
      </div>

      <Card className="p-5">
        <Label className="mb-3">What the customer gets</Label>
        <ul className="flex flex-col gap-3">
          {[
            "A launcher in the corner of every page",
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

/** Try it on a real site with nothing installed.
 *
 * A browser extension was the obvious shape for this and the wrong one: it needs
 * packaging and a store review, and it would only ever run for people who
 * installed it. A bookmarklet is the same script injected by hand — no install,
 * works on any page you can open, and it is honest about being a preview because
 * it disappears the moment you navigate.
 */
function PreviewMethod() {
  const [key, setKey] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const signedIn = useSignedIn();

  async function mintPreview() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createSiteKey({
        label: "Preview",
        allowed_origins: [],
        preview: true,
      });
      setKey(created.key);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't create a preview key.");
    } finally {
      setBusy(false);
    }
  }

  const bookmarklet = key
    ? `javascript:(function(){var s=document.createElement('script');` +
      `s.src='${API_BASE}/widget.js';s.setAttribute('data-fte-key','${key}');` +
      `document.body.appendChild(s);})();`
    : "";

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="min-w-0">
        <h2 className="mb-2 text-heading text-fg">
          See it on your own site, right now
        </h2>
        <p className="mb-4 text-[13.5px] leading-relaxed text-muted">
          A preview key and a bookmarklet. Open your storefront, click the
          bookmark, and the same widget appears over the real page — nothing
          installed, nothing changed on your site.
        </p>

        {!signedIn ? (
          <Card className="p-5 text-[13.5px] text-body">
            Sign in to mint a preview key.
          </Card>
        ) : !key ? (
          <Button onClick={mintPreview} disabled={busy}>
            {busy ? "Creating…" : "Create a preview key"}
          </Button>
        ) : (
          <>
            <CodeBlock code={bookmarklet} language="javascript" />
            <ol className="mt-4 flex flex-col gap-2 text-[13px] text-muted">
              {[
                "Copy the line above",
                "Make a new browser bookmark and paste it as the URL",
                "Open your storefront and click the bookmark",
              ].map((step, i) => (
                <li key={step} className="flex gap-2.5">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-md border border-line text-[10px] text-faint">
                    {i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </>
        )}
        {error && <p className="mt-2 text-[12px] text-alert">{error}</p>}
      </div>

      <Card className="p-5">
        <Label className="mb-3">What a preview is and isn&apos;t</Label>
        <ul className="flex flex-col gap-3 text-[13px] leading-relaxed">
          <li className="flex gap-2.5 text-body">
            <Check size={14} className="mt-0.5 shrink-0 text-ok" />
            The real widget, the real agent, your real policies
          </li>
          <li className="flex gap-2.5 text-body">
            <Check size={14} className="mt-0.5 shrink-0 text-ok" />
            Only you see it — nothing is added to your site
          </li>
          <li className="flex gap-2.5 text-muted">
            <span className="mt-0.5 shrink-0 text-warn">!</span>
            A preview key accepts any origin, so revoke it when you&apos;re done
          </li>
          <li className="flex gap-2.5 text-muted">
            <span className="mt-0.5 shrink-0 text-warn">!</span>
            Sites with a strict content-security policy will block the injected
            script; the script tag still works there
          </li>
        </ul>
      </Card>
    </div>
  );
}

/** Whether a session token exists, without tripping hydration.
 *
 * localStorage differs between the server render and the first client one, so
 * this is read from an external store rather than an effect. */
const NEVER_CHANGES = () => () => {};

function useSignedIn(): boolean {
  return React.useSyncExternalStore(
    NEVER_CHANGES,
    () => Boolean(getToken()),
    () => false,
  );
}

function ApiMethod() {
  // The public endpoint, with the site key — the one a storefront can actually
  // reach. Documenting the operator-token endpoint here would be telling sellers
  // to put an operator credential in a browser.
  const snippet = `curl -X POST ${API_BASE}/chat/public \\
  -H 'Content-Type: application/json' \\
  -H 'X-FTE-Site-Key: pk_your_site_key' \\
  -H 'Origin: https://yourstore.com' \\
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
    <div className="grid gap-5 lg:grid-cols-2 [&>*]:min-w-0">
      <div>
        <h2 className="mb-2 text-heading text-fg">Talk to it directly</h2>
        <p className="mb-4 text-[13.5px] leading-relaxed text-muted">
          One endpoint, authorised by the same site key the widget uses. Send a
          message and a session id; the session is the conversation&apos;s
          memory, so reuse it for follow-ups.
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
    platform: PLATFORMS[0],
    monthly_conversations: VOLUMES[0],
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
              ? "border-ok/40 bg-ok/12 text-ok"
              : "border-line bg-raised text-muted hover:border-line-lit hover:text-fg",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
