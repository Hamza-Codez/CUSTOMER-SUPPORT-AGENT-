"use client";

/**
 * How LIGHTRON gets onto a seller's store.
 *
 * The previous version of this page offered "four ways to put it on your store"
 * as four equal tabs. That was the audit's complaint in miniature: it read like a
 * brochure, none of the four was the actual product path, and the page never said
 * which one a seller was supposed to pick or what state they were in.
 *
 * CRITIC.md asks for two flavours instead — one that ships now, one that is
 * honestly pending — and for the onboarding hierarchy to be visible rather than
 * implied. So this page is a sequence, not a menu, and every step reports real
 * state read back from the API: the profile from /auth/me, the grounded passages
 * from /dashboard/overview, the keys from /site-keys. A step says "done" because
 * the backend says so, never because the user clicked past it.
 */

import {
  ArrowLeft,
  ArrowRight,
  Check,
  Globe,
  KeyRound,
  Loader2,
  Lock,
  Plug,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import {
  Badge,
  Button,
  Card,
  Input,
  Label,
  Textarea,
} from "@/components/ui/primitives";
import { API_BASE, ApiError, DEMO_CUSTOMER_TOKEN, api, getToken } from "@/lib/api";
import type { Account, ScannedPage, SiteKey } from "@/lib/types";
import { cn } from "@/lib/utils";

const PLATFORMS = ["Shopify", "WooCommerce", "Magento", "Custom", "Other"];
const VOLUMES = ["Under 500", "500 – 2,000", "2,000 – 10,000", "10,000+"];

type Flavour = "storefront" | "api";

/** What the storefront writes for the widget to forward.
 *
 * Not illustrative — this is the shape `LocalScrapeAdapter` actually reads. The
 * widget pulls `fte.widget.context` out of localStorage on every message and
 * posts it as `ephemeral_context`; the adapter answers order and cart questions
 * from those exact keys and falls back to the store when they are absent.
 */
const CONTEXT_SNIPPET = `<script>
  // Write what the shopper can already see on this page.
  // LIGHTRON reads it per message. Nothing here is stored on our side.
  localStorage.setItem("fte.widget.context", JSON.stringify({
    orders: [
      {
        order_id:        "ORD-1002",
        status:          "in_transit",
        placed_at:       "2026-07-21",
        eta:             "2026-07-30",
        carrier:         "DHL",
        tracking_number: "JD0002",
        item_count:      2,
        total:           "84.00",
        name:            "Ayesha K.",
        email:           "ayesha@example.com"
      }
    ],
    cart: { items: [], total: "0.00" }
  }));
</script>`;

export default function IntegrationsPage() {
  const [flavour, setFlavour] = React.useState<Flavour>("storefront");
  const signedIn = useSignedIn();
  const state = useIntegrationState(signedIn);

  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <section className="aura border-b border-line px-5 py-16">
          <div className="mx-auto max-w-5xl">
            <Link
              href="/pricing"
              className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted transition hover:text-fg"
            >
              <ArrowLeft size={14} /> Pricing
            </Link>
            <p className="text-label mb-3 uppercase text-accent">Integration</p>
            <h1 className="text-title text-fg sm:text-display">
              Put LIGHTRON on your storefront
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted">
              This is the real agent, not the demo. It answers from the pages you
              publish and the order context the shopper&apos;s own session can
              see — and when something moves money, it stops and asks a person.
            </p>
          </div>
        </section>

        <section className="px-5 py-12">
          <div className="mx-auto max-w-5xl">
            <div className="mb-3 flex items-baseline justify-between gap-4">
              <h2 className="text-heading text-fg">Choose how it connects</h2>
              <Link
                href="/demo"
                className="text-[13px] text-muted transition hover:text-fg"
              >
                Looking for the demo? →
              </Link>
            </div>
            <p className="mb-6 max-w-2xl text-[13.5px] leading-relaxed text-muted">
              Both flavours run the same agent, the same guardrails and the same
              human-approval step. They differ only in where the order data comes
              from.
            </p>

            <div className="grid gap-4 lg:grid-cols-2">
              <FlavourCard
                icon={<Globe size={17} />}
                name="Storefront mode"
                status="available"
                selected={flavour === "storefront"}
                onSelect={() => setFlavour("storefront")}
                summary="No store backend required. We read your published policy pages; the widget forwards what the shopper's session already shows."
                points={[
                  "Policies grounded from your own pages",
                  "Orders and cart read from the live session",
                  "Every refund or return becomes a Decision Card",
                ]}
              />
              <FlavourCard
                icon={<Plug size={17} />}
                name="Connected API"
                status="soon"
                selected={flavour === "api"}
                onSelect={() => setFlavour("api")}
                summary="Authenticated server-side reads against your orders API, so the agent sees every order rather than the ones on screen."
                points={[
                  "Full order history, not just the visible session",
                  "In-policy actions can execute without a card",
                  "Needs an endpoint and credentials from you",
                ]}
              />
            </div>
          </div>
        </section>

        <section className="border-t border-line bg-surface/30 px-5 py-14">
          <div className="mx-auto max-w-5xl">
            {flavour === "storefront" ? (
              <StorefrontFlavour signedIn={signedIn} state={state} />
            ) : (
              <ApiFlavour />
            )}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Real state                                                                  */
/* -------------------------------------------------------------------------- */

type IntegrationState = {
  loading: boolean;
  account: Account | null;
  /** Passages this business can actually cite. 0 means it refuses policy questions. */
  passages: number;
  keys: SiteKey[];
  error: string | null;
  refresh: () => void;
};

/** Everything the steps below report, read back from the backend.
 *
 * `allSettled` rather than `all`: a seller who has not scanned yet gets a clean
 * answer from /site-keys and an empty one from /dashboard/overview, and one
 * empty result must not blank the whole page.
 */
function useIntegrationState(signedIn: boolean): IntegrationState {
  const [loading, setLoading] = React.useState(signedIn);
  const [account, setAccount] = React.useState<Account | null>(null);
  const [passages, setPassages] = React.useState(0);
  const [keys, setKeys] = React.useState<SiteKey[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [tick, setTick] = React.useState(0);

  React.useEffect(() => {
    // `loading` already initialises to `signedIn`, so a signed-out visitor is
    // not loading and there is nothing to set here.
    if (!signedIn) return;
    let cancelled = false;
    Promise.allSettled([api.me(), api.overview(), api.siteKeys()]).then(
      ([me, overview, siteKeys]) => {
        if (cancelled) return;
        if (me.status === "fulfilled") setAccount(me.value);
        if (overview.status === "fulfilled")
          setPassages(overview.value.policies.length);
        if (siteKeys.status === "fulfilled") setKeys(siteKeys.value.keys);

        const failed = [me, overview, siteKeys].find(
          (r) => r.status === "rejected",
        ) as PromiseRejectedResult | undefined;
        setError(
          failed && me.status === "rejected"
            ? failed.reason instanceof ApiError
              ? failed.reason.message
              : "Couldn't load your integration state."
            : null,
        );
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [signedIn, tick]);

  return {
    loading,
    account,
    passages,
    keys,
    error,
    refresh: () => setTick((n) => n + 1),
  };
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

/* -------------------------------------------------------------------------- */
/* Flavour A — storefront mode                                                 */
/* -------------------------------------------------------------------------- */

function StorefrontFlavour({
  signedIn,
  state,
}: {
  signedIn: boolean;
  state: IntegrationState;
}) {
  const live = state.keys.filter((k) => k.active && !k.preview);

  // Read, never assumed. Each of these is a fact the backend reported.
  const profileDone = Boolean(state.account?.profile_completed);
  const groundedDone = state.passages > 0;
  const keyDone = live.length > 0;

  if (!signedIn) return <SignInGate />;

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:items-start">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-heading text-fg">Three steps, in this order</h2>
          <button
            onClick={state.refresh}
            className="inline-flex items-center gap-1.5 text-[12.5px] text-muted transition hover:text-fg"
          >
            <RefreshCw size={13} className={cn(state.loading && "animate-spin")} />
            Refresh
          </button>
        </div>

        {state.error && (
          <p className="rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
            {state.error}
          </p>
        )}

        <Step
          index={1}
          title="Complete your store profile"
          done={profileDone}
          loading={state.loading}
          blurb="Your store name, URL and written policies. The agent speaks as your store, so this is where it learns which store that is."
        >
          {profileDone ? (
            <p className="text-[13px] text-muted">
              Set up as{" "}
              <span className="text-body">{state.account?.business_name}</span>.{" "}
              <Link href="/onboarding" className="text-accent-soft hover:underline">
                Update it
              </Link>
            </p>
          ) : (
            <Link
              href="/onboarding"
              className="action inline-flex h-10 items-center gap-2 rounded-xl px-4 text-[13px] font-medium"
            >
              Complete profile <ArrowRight size={14} />
            </Link>
          )}
        </Step>

        <Step
          index={2}
          title="Ground it in your own pages"
          done={groundedDone}
          loading={state.loading}
          blurb="We read your published policy pages and keep the passages the agent may quote. Until this runs it has nothing grounded to say, and correctly refuses policy questions."
        >
          <ScanPanel passages={state.passages} onImported={state.refresh} />
        </Step>

        <Step
          index={3}
          title="Install it on your storefront"
          done={keyDone}
          loading={state.loading}
          blurb="One script tag, locked to your domain. The launcher renders in a shadow root, so it can neither inherit your CSS nor leak its own."
        >
          <KeyPanel keys={state.keys} onChanged={state.refresh} />
        </Step>

        <ContextPanel />
      </div>

      <div className="flex flex-col gap-4">
        <ReadinessCard
          profileDone={profileDone}
          groundedDone={groundedDone}
          keyDone={keyDone}
          passages={state.passages}
          liveKeys={live.length}
        />
        <BoundariesCard />
      </div>
    </div>
  );
}

function SignInGate() {
  return (
    <Card accent className="mx-auto max-w-lg p-7 text-center">
      <span className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-accent/12 text-accent-soft">
        <KeyRound size={19} />
      </span>
      <h3 className="mb-2 text-[15px] font-semibold text-fg">
        Integration belongs to an account
      </h3>
      <p className="mb-5 text-[13px] leading-relaxed text-muted">
        Keys, grounded passages and the operator queue are all scoped to your
        store, so this needs you signed in.
      </p>
      <div className="flex justify-center gap-2">
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
  );
}

/** Scan the seller's site, let them choose, then write the passages.
 *
 * Scanning and importing are deliberately two actions. The backend's own note on
 * /onboarding/scan is the reason: what the agent may quote at a customer should
 * never be decided by a heuristic that ran unattended. So nothing is stored
 * until a person has ticked the pages.
 */
function ScanPanel({
  passages,
  onImported,
}: {
  passages: number;
  onImported: () => void;
}) {
  const [url, setUrl] = React.useState("");
  const [pages, setPages] = React.useState<ScannedPage[] | null>(null);
  const [chosen, setChosen] = React.useState<Set<string>>(new Set());
  const [note, setNote] = React.useState<string>("");
  const [busy, setBusy] = React.useState<"scan" | "import" | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [imported, setImported] = React.useState<number | null>(null);

  async function scan(event: React.FormEvent) {
    event.preventDefault();
    setBusy("scan");
    setError(null);
    setImported(null);
    try {
      const result = await api.scanSite(url.trim());
      setPages(result.pages);
      setNote(result.note);
      // Everything found is pre-selected: the seller is confirming, not building
      // the list from scratch.
      setChosen(new Set(result.pages.map((p) => p.url)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't read that site.");
    } finally {
      setBusy(null);
    }
  }

  async function importChosen() {
    const picked = (pages ?? []).filter((p) => chosen.has(p.url));
    if (!picked.length) return;
    setBusy("import");
    setError(null);
    try {
      const result = await api.onboardingContext(
        picked.map((p) => ({ topic: p.topic, body: p.text })),
      );
      setImported(result.passages);
      setPages(null);
      onImported();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save those pages.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {passages > 0 && (
        <p className="text-[13px] text-muted">
          <span className="text-ok">{passages}</span> passage
          {passages === 1 ? "" : "s"} the agent can cite today. Scanning again adds
          to them.
        </p>
      )}

      <form onSubmit={scan} className="flex flex-wrap gap-2">
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://yourstore.com"
          aria-label="Your storefront URL"
          className="min-w-52 flex-1"
        />
        <Button type="submit" disabled={busy !== null || !url.trim()}>
          {busy === "scan" ? (
            <>
              <Loader2 size={14} className="animate-spin" /> Reading…
            </>
          ) : (
            "Scan my site"
          )}
        </Button>
      </form>

      {imported !== null && (
        <p className="rounded-xl border border-ok/25 bg-ok/[0.06] p-3 text-[13px] text-ok">
          Saved {imported} passage{imported === 1 ? "" : "s"}. The agent will
          answer from these, and only these.
        </p>
      )}

      {pages !== null && (
        <div className="flex flex-col gap-2">
          {pages.length === 0 ? (
            <p className="text-[13px] leading-relaxed text-muted">
              {note || "Nothing on that site looked like a policy page."} You can
              still paste your policies by hand in{" "}
              <Link href="/onboarding" className="text-accent-soft hover:underline">
                onboarding
              </Link>
              .
            </p>
          ) : (
            <>
              <Label>
                Found {pages.length} page{pages.length === 1 ? "" : "s"} — tick
                what it may quote
              </Label>
              <ul className="flex flex-col gap-1.5">
                {pages.map((page) => {
                  const on = chosen.has(page.url);
                  return (
                    <li key={page.url}>
                      <button
                        type="button"
                        aria-pressed={on}
                        onClick={() =>
                          setChosen((prev) => {
                            const next = new Set(prev);
                            if (on) next.delete(page.url);
                            else next.add(page.url);
                            return next;
                          })
                        }
                        className={cn(
                          "flex w-full items-start gap-2.5 rounded-xl border p-3 text-left transition",
                          on
                            ? "border-ok/40 bg-ok/[0.07]"
                            : "border-line bg-raised hover:border-line-lit",
                        )}
                      >
                        <span
                          className={cn(
                            "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                            on
                              ? "border-ok/50 bg-ok/20 text-ok"
                              : "border-line text-transparent",
                          )}
                        >
                          <Check size={11} />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-[13px] text-body">
                            {page.topic}
                          </span>
                          <span className="mt-0.5 block break-all text-[11.5px] text-faint">
                            {page.url}
                          </span>
                          <span className="mt-1 block text-[11.5px] text-muted">
                            matched on {page.matched}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <Button
                onClick={importChosen}
                disabled={busy !== null || chosen.size === 0}
                className="self-start"
              >
                {busy === "import" ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Saving…
                  </>
                ) : (
                  `Ground on ${chosen.size} page${chosen.size === 1 ? "" : "s"}`
                )}
              </Button>
            </>
          )}
        </div>
      )}

      {error && <p className="text-[12px] text-alert">{error}</p>}
    </div>
  );
}

/** Mints a real key and shows the real snippet.
 *
 * Everything below comes back from the API: the key, the origins it is locked
 * to, and the exact line to paste, assembled server-side so a copied snippet
 * cannot disagree with itself.
 */
function KeyPanel({
  keys,
  onChanged,
}: {
  keys: SiteKey[];
  onChanged: () => void;
}) {
  const [origin, setOrigin] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);

  const live = keys.filter((k) => k.active && !k.preview);
  // Shown, not hidden. A revoked key disappearing from this page is why a dead
  // key sitting in a live site's HTML is invisible.
  const revoked = keys.filter((k) => !k.active && !k.preview);

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
      onChanged();
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
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't revoke that key.");
    }
  }

  async function mintPreview() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createSiteKey({
        label: "Preview",
        allowed_origins: [],
        preview: true,
      });
      setPreview(created.key);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Couldn't create a preview key.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {live.length > 0 ? (
        <div className="flex min-w-0 flex-col gap-4">
          <Label>
            {live.length === 1 ? "Your snippet" : `Your snippets (${live.length})`}
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
          No key yet. Add the domain your storefront runs on:
        </p>
      )}

      <form onSubmit={mint} className="flex flex-wrap gap-2">
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
      <p className="text-[12px] leading-relaxed text-faint">
        Include <code className="text-accent-soft">http://</code> or{" "}
        <code className="text-accent-soft">https://</code>, and the port if there
        is one. The match is exact, so{" "}
        <code className="text-accent-soft">http://localhost:3000</code> will not
        match a page served over <code className="text-accent-soft">https</code>.
      </p>

      <div className="mt-1 rounded-xl border border-line bg-raised p-4">
        <p className="mb-1.5 text-[13px] font-medium text-fg">
          Try it before you edit your theme
        </p>
        <p className="mb-3 text-[12.5px] leading-relaxed text-muted">
          A preview key accepts any origin. Save the line below as a bookmark,
          open your storefront and click it — the real widget appears over the
          real page, with nothing installed.
        </p>
        {preview ? (
          <>
            <CodeBlock
              code={
                `javascript:(function(){var s=document.createElement('script');` +
                `s.src='${API_BASE}/widget.js';s.setAttribute('data-fte-key','${preview}');` +
                `document.body.appendChild(s);})();`
              }
              language="javascript"
            />
            <p className="mt-2 text-[12px] text-warn">
              Revoke it when you&apos;re done — it is not locked to a domain.
            </p>
          </>
        ) : (
          <Button variant="secondary" onClick={mintPreview} disabled={busy}>
            {busy ? "Creating…" : "Create a preview key"}
          </Button>
        )}
      </div>

      {error && <p className="text-[12px] text-alert">{error}</p>}

      {revoked.length > 0 && (
        <details className="text-[12px] text-faint">
          <summary className="cursor-pointer">
            {revoked.length} revoked key{revoked.length === 1 ? "" : "s"}
          </summary>
          <p className="mt-2 leading-relaxed">
            If your site still shows &ldquo;this site key has been revoked&rdquo;,
            one of these is the key in your script tag. Replace it with a live one
            above.
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {revoked.map((key) => (
              <li key={key.key} className="break-all font-mono">
                {key.key}
                {key.label && <span className="font-sans"> — {key.label}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** The second kind of data: what only the shopper's own session can see. */
function ContextPanel() {
  return (
    <Card className="p-5">
      <div className="mb-2 flex items-center gap-2">
        <Sparkles size={15} className="text-accent-soft" />
        <h3 className="text-[14px] font-semibold text-fg">
          Optional: let it see the order on screen
        </h3>
      </div>
      <p className="mb-4 text-[13px] leading-relaxed text-muted">
        Storefront mode has no server-side view of your orders. If your pages
        already know what the shopper is looking at, write it to localStorage
        under <code className="text-accent-soft">fte.widget.context</code> and the
        widget forwards it with each message. Skip this and the agent simply says
        it cannot see the order rather than guessing.
      </p>
      <CodeBlock code={CONTEXT_SNIPPET} />
      <p className="mt-3 text-[12px] leading-relaxed text-faint">
        Read per message and never persisted on our side. It lives in your
        shopper&apos;s browser, so it clears when they do.
      </p>
    </Card>
  );
}

function ReadinessCard({
  profileDone,
  groundedDone,
  keyDone,
  passages,
  liveKeys,
}: {
  profileDone: boolean;
  groundedDone: boolean;
  keyDone: boolean;
  passages: number;
  liveKeys: number;
}) {
  const ready = profileDone && groundedDone && keyDone;
  const rows = [
    { label: "Store profile", done: profileDone, detail: profileDone ? "complete" : "not yet" },
    {
      label: "Grounded passages",
      done: groundedDone,
      detail: `${passages} stored`,
    },
    { label: "Live site key", done: keyDone, detail: `${liveKeys} active` },
  ];

  return (
    <Card accent className="p-5">
      <Label className="mb-3">Where you stand</Label>
      <ul className="flex flex-col gap-2.5">
        {rows.map((row) => (
          <li key={row.label} className="flex items-center gap-2.5 text-[13px]">
            <span
              className={cn(
                "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                row.done
                  ? "border-ok/50 bg-ok/15 text-ok"
                  : "border-line text-transparent",
              )}
            >
              <Check size={10} />
            </span>
            <span className={row.done ? "text-body" : "text-muted"}>
              {row.label}
            </span>
            <span className="ml-auto text-[12px] text-faint">{row.detail}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 border-t border-line pt-4">
        {ready ? (
          <p className="text-[13px] leading-relaxed text-ok">
            Live. The widget on your storefront is answering from your pages.
          </p>
        ) : (
          <p className="text-[13px] leading-relaxed text-muted">
            The widget will load as soon as a key exists, but it can only answer
            policy questions once step 2 has stored something.
          </p>
        )}
      </div>
    </Card>
  );
}

/** What it will not do, stated where a seller decides to install it. */
function BoundariesCard() {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck size={15} className="text-ok" />
        <Label className="mb-0">Where it stops</Label>
      </div>
      <ul className="flex flex-col gap-3 text-[13px] leading-relaxed">
        {[
          "Identity is checked before any order detail is shown",
          "Refunds and returns pause for a human in storefront mode — always",
          "A policy question with no stored passage is refused, not guessed",
          "The key works only from the domains you listed",
        ].map((item) => (
          <li key={item} className="flex gap-2.5 text-body">
            <Check size={14} className="mt-0.5 shrink-0 text-ok" />
            {item}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Flavour B — connected API                                                   */
/* -------------------------------------------------------------------------- */

function ApiFlavour() {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start">
      <div className="min-w-0">
        <div className="mb-3 flex items-center gap-2">
          <Lock size={16} className="text-warn" />
          <h2 className="text-heading text-fg">Not open yet</h2>
        </div>
        <p className="mb-4 max-w-xl text-[14px] leading-relaxed text-muted">
          Connected mode gives the agent authenticated server-side reads, so it
          answers about orders the shopper is not currently looking at, and can
          settle an in-policy refund without a card. It needs an adapter written
          against your platform, which is why it is a conversation rather than a
          button.
        </p>
        <p className="mb-6 max-w-xl text-[13px] leading-relaxed text-faint">
          The tool layer already calls a{" "}
          <code className="text-accent-soft">DataAdapter</code> interface rather
          than a data source, so switching a store from storefront mode to
          connected mode changes one binding — not the agent, the guardrails, or
          the approval flow.
        </p>
        <h3 className="mb-3 text-[14px] font-semibold text-fg">
          Tell us where your orders live
        </h3>
        <RequestForm />
      </div>

      <Card className="p-5">
        <Label className="mb-3">What we&apos;ll ask for</Label>
        <ul className="flex flex-col gap-3 text-[13px] leading-relaxed text-body">
          {[
            "How orders are exposed — REST, GraphQL or a direct read",
            "How a customer proves who they are",
            "Which actions you want settled automatically, and the ceiling",
            "The domains the widget will run on",
          ].map((item) => (
            <li key={item} className="flex gap-2.5">
              <ArrowRight size={13} className="mt-1 shrink-0 text-accent-soft" />
              {item}
            </li>
          ))}
        </ul>
        <p className="mt-4 border-t border-line pt-4 text-[12px] leading-relaxed text-faint">
          In the meantime storefront mode runs the same agent on the same
          guardrails — it just stops more often.
        </p>
      </Card>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Shared pieces                                                               */
/* -------------------------------------------------------------------------- */

function FlavourCard({
  icon,
  name,
  status,
  summary,
  points,
  selected,
  onSelect,
}: {
  icon: React.ReactNode;
  name: string;
  status: "available" | "soon";
  summary: string;
  points: string[];
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "rounded-2xl border p-5 text-left transition",
        selected
          ? "border-accent/45 bg-accent/[0.07]"
          : "border-line bg-raised hover:border-line-lit",
      )}
    >
      <div className="mb-2.5 flex items-center gap-2.5">
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-xl",
            status === "available"
              ? "bg-ok/12 text-ok"
              : "bg-warn/12 text-warn",
          )}
        >
          {icon}
        </span>
        <h3 className="text-[15px] font-semibold text-fg">{name}</h3>
        <Badge tone={status === "available" ? "ok" : "warn"} className="ml-auto">
          {status === "available" ? "Available" : "Coming soon"}
        </Badge>
      </div>
      <p className="mb-3.5 text-[13px] leading-relaxed text-muted">{summary}</p>
      <ul className="flex flex-col gap-2">
        {points.map((point) => (
          <li key={point} className="flex gap-2 text-[12.5px] text-body">
            <Check size={13} className="mt-0.5 shrink-0 text-faint" />
            {point}
          </li>
        ))}
      </ul>
    </button>
  );
}

function Step({
  index,
  title,
  blurb,
  done,
  loading,
  children,
}: {
  index: number;
  title: string;
  blurb: string;
  done: boolean;
  loading: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="mb-2 flex items-start gap-3">
        <span
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-[11px] font-medium",
            done
              ? "border-ok/45 bg-ok/15 text-ok"
              : "border-line bg-raised text-faint",
          )}
        >
          {done ? <Check size={12} /> : index}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[14.5px] font-semibold text-fg">{title}</h3>
            {loading ? (
              <Loader2 size={12} className="animate-spin text-faint" />
            ) : (
              done && <Badge tone="ok">Done</Badge>
            )}
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{blurb}</p>
        </div>
      </div>
      <div className="mt-4 min-w-0 pl-0 sm:pl-9">{children}</div>
    </Card>
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
      setError(err instanceof ApiError ? err.message : "Could not send that.");
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
              onChange={(e) =>
                setForm({ ...form, contact_email: e.target.value })
              }
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

        <Labelled label="How your orders are exposed">
          <Textarea
            rows={3}
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="REST, GraphQL, direct database read, what auth it needs…"
          />
        </Labelled>

        {error && (
          <p className="rounded-xl border border-alert/25 bg-alert/[0.06] p-3 text-[13px] text-alert">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" disabled={!ready || sending}>
          {sending ? "Sending…" : "Request connected mode"}
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
