import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Clock,
  MessagesSquare,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

/* Server-rendered and static: this page is the pitch and needs to stay
 * indexable, so nothing here is a client component. */

export default function HomePage() {
  return (
    <>
      <SiteHeader />

      <main className="flex-1">
        <section className="surface-gradient border-b border-line px-4 py-20 sm:px-6 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <span className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-[12px] text-accent-soft">
              <BadgeCheck size={12} /> Grounded in your data, not the model&apos;s
              guesses
            </span>
            <h1 className="text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-fg sm:text-5xl">
              Hire a digital employee for your storefront
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-pretty text-[15px] leading-relaxed text-muted sm:text-base">
              Not a chatbot that answers questions. An employee that does the
              job: it reads your real orders, applies your own written policies,
              settles what it can, and prepares the rest for you to approve in
              one click.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/demo"
                className="inline-flex h-12 items-center gap-2 rounded-xl bg-accent px-6 text-[15px] font-medium text-white transition hover:bg-accent-soft"
              >
                Try the demo <ArrowRight size={16} />
              </Link>
              <Link
                href="/features"
                className="inline-flex h-12 items-center rounded-xl border border-line px-6 text-[15px] text-body transition hover:border-accent/50"
              >
                See features
              </Link>
            </div>
          </div>
        </section>

        <Section
          eyebrow="The problem"
          title="Generic bots make support worse"
          lead="They invent answers, cannot touch a real order, and cannot take a single meaningful action. The customer ends up waiting for a human anyway — after being told something untrue."
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <Point title="Invents answers">
              Confident, wrong policy is worse than no answer at all.
            </Point>
            <Point title="Cannot act">
              No order lookup, no refund, no escalation with context.
            </Point>
            <Point title="Escalates blind">
              A human inherits a transcript and starts from nothing.
            </Point>
          </div>
        </Section>

        <Section
          eyebrow="How it works"
          title="Specialists, not one do-everything bot"
          lead="A coordinator reads what the customer wants and hands it to the right specialist. Each one has a tight job, a small set of tools, and rules it cannot talk its way around."
          alt
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Feature icon={<MessagesSquare size={16} />} title="Orders">
              Verifies identity before revealing anything, then reports real
              status, carrier and ETA.
            </Feature>
            <Feature icon={<BookOpen size={16} />} title="Support">
              Answers from your written policy and cites the passage. No source,
              no claim.
            </Feature>
            <Feature icon={<Wrench size={16} />} title="Products">
              Explains and compares what you actually stock, including when
              something is out of it.
            </Feature>
            <Feature icon={<ShieldCheck size={16} />} title="Refunds">
              Applies your policy, settles the small and recent ones, escalates
              the rest.
            </Feature>
          </div>
        </Section>

        <Section
          eyebrow="The dual dashboard"
          title="See both sides of the conversation"
          lead="One window, two lenses. Watch the FTE stop short of a refund it should not make on its own, flip to the seller view, and find the decision already prepared and waiting."
        >
          <div className="overflow-hidden rounded-2xl border border-line bg-surface">
            <div className="h-px hairline" />
            <div className="grid divide-y divide-line sm:grid-cols-2 sm:divide-x sm:divide-y-0">
              <div className="p-5">
                <p className="mb-2 text-[11px] uppercase tracking-wider text-faint">
                  Customer view
                </p>
                <p className="text-[13px] leading-relaxed text-body">
                  &ldquo;I&apos;ve passed this to a colleague to review, because
                  it needs a person to sign it off. I haven&apos;t taken any
                  money-related action in the meantime.&rdquo;
                </p>
              </div>
              <div className="p-5">
                <p className="mb-2 text-[11px] uppercase tracking-wider text-faint">
                  Seller view
                </p>
                <p className="mb-2 text-[13px] leading-relaxed text-body">
                  Refund 149.00 for ORD-1001 — customer verified.
                </p>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-warn/25 bg-warn/10 px-2.5 py-1 text-[11px] text-warn">
                  <Clock size={11} /> Above the automatic refund limit
                </span>
              </div>
            </div>
          </div>
        </Section>

        <Section
          eyebrow="Why you can trust it"
          title="Controls in code, not in a prompt"
          lead="A prompt is a request, and a request can be declined. The limits that matter are enforced outside the model, where nothing can argue with them."
          alt
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <Point title="Identity first">
              Nothing about an account is revealed until the order and email
              match.
            </Point>
            <Point title="Money is human-owned">
              Above your cap or outside your window, the run pauses for a person.
            </Point>
            <Point title="Everything is logged">
              Every sensitive read and write, including the refusals.
            </Point>
          </div>
        </Section>

        <section className="border-t border-line px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
              A full-time employee for the price of lunch
            </h2>
            <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-muted">
              From 20 a month. Full frontline support, with a human on the calls
              that matter.
            </p>
            <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/pricing"
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-accent px-5 text-sm font-medium text-white transition hover:bg-accent-soft"
              >
                See pricing <ArrowRight size={15} />
              </Link>
              <Link
                href="/demo"
                className="inline-flex h-11 items-center rounded-xl border border-line px-5 text-sm text-body transition hover:border-accent/50"
              >
                Try the demo
              </Link>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}

function Section({
  eyebrow,
  title,
  lead,
  children,
  alt = false,
}: {
  eyebrow: string;
  title: string;
  lead: string;
  children: React.ReactNode;
  alt?: boolean;
}) {
  return (
    <section
      className={`border-b border-line px-4 py-16 sm:px-6 ${alt ? "bg-surface/30" : ""}`}
    >
      <div className="mx-auto max-w-5xl">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-accent">
          {eyebrow}
        </p>
        <h2 className="max-w-2xl text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
          {title}
        </h2>
        <p className="mb-8 mt-3 max-w-2xl text-pretty text-[15px] leading-relaxed text-muted">
          {lead}
        </p>
        {children}
      </div>
    </section>
  );
}

function Point({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      <p className="mb-1.5 text-sm font-medium text-fg">{title}</p>
      <p className="text-[13px] leading-relaxed text-muted">{children}</p>
    </div>
  );
}

function Feature({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3.5 rounded-2xl border border-line bg-surface p-5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/12 text-accent">
        {icon}
      </span>
      <div>
        <p className="mb-1 text-sm font-medium text-fg">{title}</p>
        <p className="text-[13px] leading-relaxed text-muted">{children}</p>
      </div>
    </div>
  );
}
