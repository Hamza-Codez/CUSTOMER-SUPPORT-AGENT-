import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Boxes,
  Clock,
  Lock,
  PackageSearch,
  Route,
  ShieldAlert,
  Undo2,
} from "lucide-react";
import Link from "next/link";

import { Mark } from "@/components/Brand";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { brand, voice } from "@/lib/brand";
import { TOOLS, type ToolId } from "@/lib/tools";

/* Static and server-rendered: this page is the pitch and needs to stay
 * indexable, so nothing here is a client component. */

const TOOL_ICONS: Record<ToolId, React.ReactNode> = {
  route: <Route size={15} />,
  order_lookup: <PackageSearch size={15} />,
  policy_retriever: <BookOpen size={15} />,
  product_catalog: <Boxes size={15} />,
  refund_processor: <Undo2 size={15} />,
  human_escalation: <ShieldAlert size={15} />,
  send_summary_email: <BadgeCheck size={15} />,
};

export default function HomePage() {
  return (
    <>
      <SiteHeader />

      <main className="flex-1">
        {/* Hero */}
        <section className="aura relative overflow-hidden border-b border-line px-5 pb-20 pt-20 sm:pb-28 sm:pt-28">
          <div className="grid-field pointer-events-none absolute inset-0 opacity-40" />
          <div className="relative mx-auto max-w-5xl">
            <div className="mx-auto max-w-2xl text-center">
              <span className="mb-6 inline-flex items-center gap-2 rounded-lg border border-accent/25 bg-accent/[0.08] px-3 py-1.5 text-[12px] text-accent-soft">
                <BadgeCheck size={12} /> {voice.grounded}
              </span>
              <h1 className="text-title text-gradient sm:text-display">
                {voice.notAChatbot}
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-pretty text-[15.5px] leading-relaxed text-muted">
                {brand.promise}
              </p>
              <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                <Link
                  href="/demo"
                  className="action inline-flex h-12 items-center gap-2 rounded-xl px-6 text-[15px] font-medium transition active:translate-y-px"
                >
                  Watch it work <ArrowRight size={16} />
                </Link>
                <Link
                  href="/signup"
                  className="inline-flex h-12 items-center rounded-xl border border-line bg-raised px-6 text-[15px] text-body transition hover:border-line-lit"
                >
                  Create an account
                </Link>
              </div>
              <p className="mt-4 text-[12px] text-faint">
                No card. The demo needs no account at all.
              </p>
            </div>

            {/* The moment that sells it, shown rather than described. */}
            <div className="panel-raised mx-auto mt-16 max-w-3xl overflow-hidden rounded-2xl">
              <div className="h-px hairline" />
              <div className="grid divide-y divide-line md:grid-cols-2 md:divide-x md:divide-y-0">
                <div className="p-6">
                  <p className="text-label mb-3 uppercase text-faint">
                    What the customer sees
                  </p>
                  <div className="flex gap-3">
                    <Mark size={24} className="mt-0.5 shrink-0" />
                    <p className="text-[13.5px] leading-relaxed text-body">
                      &ldquo;I&apos;ve passed this to a colleague to review, because
                      it needs a person to sign it off. I haven&apos;t taken any
                      money-related action in the meantime.&rdquo;
                    </p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Chip tone="neutral">Routed to Refunds</Chip>
                    <Chip tone="ok">Policy cited</Chip>
                    <Chip tone="warn">Waiting for approval</Chip>
                  </div>
                </div>

                <div className="p-6">
                  <p className="text-label mb-3 uppercase text-faint">
                    What you see, at the same moment
                  </p>
                  <p className="text-[13.5px] font-medium text-fg">
                    Refund 149.00 — ORD-1001
                  </p>
                  <p className="mt-1 text-[12.5px] text-muted">
                    Ayesha K. · verified by order and email
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Chip tone="warn">
                      <Clock size={10} /> Above the automatic limit
                    </Chip>
                  </div>
                  <div className="mt-4 flex gap-2">
                    <span className="action rounded-lg px-3 py-1.5 text-[12px] font-medium">
                      Approve
                    </span>
                    <span className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-muted">
                      Decline
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* The tools — the thing that makes it an employee rather than a box */}
        <section className="aura-muted relative overflow-hidden border-b border-line px-5 py-20">
          <div className="mx-auto max-w-5xl">
            <p className="text-label mb-3 uppercase text-accent">
              What it can actually do
            </p>
            <h2 className="max-w-2xl text-title text-fg">
              Seven capabilities, three of which it is not allowed to use alone
            </h2>
            <p className="mb-10 mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">
              A chatbot has a prompt. This has tools — the only door between the
              model and your data, each one audited, and the ones that move money
              gated in code rather than in an instruction.
            </p>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {TOOLS.map((tool) => (
                <div
                  key={tool.id}
                  className="panel group rounded-2xl p-5 transition hover:border-accent/30"
                >
                  <div className="mb-3 flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-raised text-accent-soft transition group-hover:border-accent/40 group-hover:bg-accent/12">
                      {TOOL_ICONS[tool.id]}
                    </span>
                    <span className="text-[13.5px] font-medium text-fg">
                      {tool.name}
                    </span>
                    {tool.gated && (
                      <span
                        title="Gated — enforced in code"
                        className="ml-auto text-faint"
                      >
                        <Lock size={11} />
                      </span>
                    )}
                  </div>
                  <p className="text-[12.5px] leading-relaxed text-muted">
                    {tool.blurb}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Why it can be trusted */}
        <section className="border-b border-line bg-surface/30 px-5 py-20">
          <div className="mx-auto max-w-5xl">
            <p className="text-label mb-3 uppercase text-accent">
              Why it can be trusted
            </p>
            <h2 className="max-w-2xl text-title text-fg">
              Controls in code, not in a prompt
            </h2>
            <p className="mb-10 mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">
              A prompt is a request, and a request can be declined. We watched a
              model ignore an explicit instruction and invent product prices — so
              the limits that matter live where nothing can argue with them.
            </p>

            <div className="grid gap-3 sm:grid-cols-3">
              <Pillar title="Identity before data">
                Nothing about an account appears until the order number and the
                email on it match. Checked in the tool, not the prompt.
              </Pillar>
              <Pillar title="Money is yours">
                Above your cap, outside your window, or not yet delivered — it
                stops and prepares the decision instead.
              </Pillar>
              <Pillar title="No source, no claim">
                An answer that cannot be traced to one of your documents is
                withheld before the customer sees it.
              </Pillar>
            </div>
          </div>
        </section>

        {/* Close */}
        <section className="aura-bottom relative overflow-hidden px-5 py-24">
          <div className="mx-auto max-w-2xl text-center">
            <Mark size={40} className="mx-auto mb-6" />
            <h2 className="text-title text-fg">
              Easier to believe once you&apos;ve watched it
            </h2>
            <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-muted">
              Ask it for a refund it shouldn&apos;t approve, then flip to the
              seller&apos;s side and find the decision already waiting for you.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/demo"
                className="action inline-flex h-12 items-center gap-2 rounded-xl px-6 text-[15px] font-medium transition active:translate-y-px"
              >
                Try the demo <ArrowRight size={16} />
              </Link>
              <Link
                href="/pricing"
                className="inline-flex h-12 items-center rounded-xl border border-line px-6 text-[15px] text-body transition hover:border-line-lit"
              >
                See pricing
              </Link>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}

function Chip({
  tone,
  children,
}: {
  tone: "neutral" | "ok" | "warn";
  children: React.ReactNode;
}) {
  const tones = {
    neutral: "border-line bg-raised text-muted",
    ok: "border-ok/25 bg-ok/[0.08] text-ok",
    warn: "border-warn/25 bg-warn/[0.08] text-warn",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[11px] font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function Pillar({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="panel rounded-2xl p-5">
      <p className="mb-2 text-[14px] font-medium text-fg">{title}</p>
      <p className="text-[13px] leading-relaxed text-muted">{children}</p>
    </div>
  );
}
