import type { Metadata } from "next";
import { Check, Minus } from "lucide-react";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { brand } from "@/lib/brand";

export const metadata: Metadata = {
  title: "Pricing",
  description: `Two plans for ${brand.name}. Core at 20 a month for hosted frontline support; Pro adds embedding on your own site, higher automation limits and team seats.`,
};

/* SPEC §16 leaves the Pro price and the conversation allowances open, so they
 * are marked as proposed rather than printed as if they were decided. */

type Row = {
  label: string;
  core: string | boolean;
  pro: string | boolean;
};

const ROWS: Row[] = [
  { label: "Hosted dual dashboard", core: true, pro: true },
  { label: "Embedded on your own site", core: false, pro: true },
  { label: "All five specialist agents", core: true, pro: true },
  { label: "Conversations included", core: "1,000 / mo", pro: "10,000 / mo" },
  { label: "Knowledge base documents", core: "Up to 25", pro: "Unlimited" },
  { label: "Refund auto-approval cap", core: "Fixed", pro: "Configurable" },
  { label: "Decision Cards", core: true, pro: "Priority routing" },
  { label: "Operator seats", core: "1", pro: "Unlimited" },
  { label: "Summary + feedback email", core: "Standard theme", pro: "Your branding" },
  { label: "Analytics", core: "Deflection, CSAT", pro: "Full + cost per conversation" },
  { label: "Audit log retention", core: "90 days", pro: "Extended" },
  { label: "Support", core: "Standard", pro: "Priority" },
];

export default function PricingPage() {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <section className="aura relative overflow-hidden border-b border-line px-5 py-16 sm:py-20">
          <div className="grid-field pointer-events-none absolute inset-0 opacity-40" />
          <div className="relative mx-auto max-w-2xl text-center">
            <h1 className="text-title text-gradient sm:text-display">
              A full-time employee for the price of lunch
            </h1>
            <p className="mx-auto mt-4 max-w-lg text-pretty text-[15px] leading-relaxed text-muted">
              Pay monthly, or yearly for two months free. Every plan includes the
              human-approval flow — that is not an upsell.
            </p>
          </div>
        </section>

        <section className="border-b border-line px-5 py-14">
          <div className="mx-auto grid max-w-3xl gap-4 sm:grid-cols-2">
            <Plan
              name="Core"
              price="20"
              cadence="per month"
              yearly="or 192 a year — two months free"
              blurb="Solo sellers and small stores getting started."
              cta="Try the demo"
            />
            <Plan
              name="Pro"
              price="49"
              cadence="per month"
              yearly="yearly discount available"
              blurb="Growing stores that want it embedded and automating more."
              cta="Request access"
              href="/integrations"
              featured
              note="Proposed — final pricing follows model-cost testing."
            />
          </div>
        </section>

        <section className="px-5 py-14">
          <div className="mx-auto max-w-3xl">
            <h2 className="mb-6 text-heading text-fg">What is in each plan</h2>
            <div className="panel overflow-hidden rounded-2xl">
              <div className="h-px hairline" />
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="text-label border-b border-line uppercase text-faint">
                    <th className="px-4 py-3 font-medium sm:px-5">Feature</th>
                    <th className="w-28 px-3 py-3 font-medium sm:w-40">Core</th>
                    <th className="w-28 px-3 py-3 font-medium sm:w-40">Pro</th>
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr
                      key={row.label}
                      className="border-b border-line-soft last:border-0"
                    >
                      <th
                        scope="row"
                        className="px-4 py-3 font-normal text-body sm:px-5"
                      >
                        {row.label}
                      </th>
                      <Cell value={row.core} />
                      <Cell value={row.pro} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-[12px] text-faint">
              Conversation allowances are indicative while usage is being costed.
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

function Cell({ value }: { value: string | boolean }) {
  return (
    <td className="px-3 py-3 text-muted">
      {value === true ? (
        <Check size={15} className="text-ok" aria-label="Included" />
      ) : value === false ? (
        <Minus size={15} className="text-faint" aria-label="Not included" />
      ) : (
        value
      )}
    </td>
  );
}

function Plan({
  name,
  price,
  cadence,
  yearly,
  blurb,
  cta,
  href = "/demo",
  featured = false,
  note,
}: {
  name: string;
  price: string;
  cadence: string;
  yearly: string;
  blurb: string;
  cta: string;
  href?: string;
  featured?: boolean;
  note?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-2xl ${
        featured
          ? "panel-raised border-accent/40 shadow-glow"
          : "panel"
      }`}
    >
      {featured && <div className="h-px hairline" />}
      <div className="p-6">
        <p className="text-sm font-medium text-fg">{name}</p>
        <p className="mt-3 flex items-baseline gap-1.5">
          <span className="text-title text-fg">{price}</span>
          <span className="text-[13px] text-faint">{cadence}</span>
        </p>
        <p className="mt-1 text-[12px] text-accent-soft">{yearly}</p>
        <p className="mt-4 text-[13px] leading-relaxed text-muted">{blurb}</p>
        <Link
          href={href}
          className={`mt-5 inline-flex h-10 w-full items-center justify-center rounded-xl text-sm font-medium transition active:translate-y-px ${
            featured
              ? "action"
              : "border border-line bg-raised text-body hover:border-line-lit"
          }`}
        >
          {cta}
        </Link>
        {note && <p className="mt-3 text-[11px] text-faint">{note}</p>}
      </div>
    </div>
  );
}
