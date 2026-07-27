import type { Metadata } from "next";
import {
  BadgeCheck,
  BookOpen,
  Clock,
  Lock,
  Mail,
  MessagesSquare,
  PackageSearch,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { Mark } from "@/components/Brand";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { brand } from "@/lib/brand";
import { TOOLS } from "@/lib/tools";

export const metadata: Metadata = {
  title: "Features",
  description: `What ${brand.name} actually does: verified order tracking, grounded policy answers, product comparison, policy-checked refunds with human approval, and a themed summary email with a feedback loop.`,
};

const JOBS = [
  {
    icon: <MessagesSquare size={16} />,
    title: "Verified order tracking",
    body: "Asks for the order number and the email on it, and reveals nothing until they match. Then reports the real status, carrier, tracking number and ETA in plain language.",
  },
  {
    icon: <BookOpen size={16} />,
    title: "Answers from your own documents",
    body: "Your policy files are parsed into passages and cited by name. If a question isn't covered, it says so and offers a colleague rather than inventing a plausible rule.",
  },
  {
    icon: <PackageSearch size={16} />,
    title: "Product explanations and comparisons",
    body: "Describes what you actually stock, with real prices and availability — including saying plainly when something is out of stock.",
  },
  {
    icon: <ShieldCheck size={16} />,
    title: "Refunds inside your policy",
    body: "Small, recent, in-policy refunds complete straight away. Anything above your cap or outside your window stops and waits for a person.",
  },
  {
    icon: <Clock size={16} />,
    title: "Decision Cards for the rest",
    body: "A paused refund arrives as a card: verified customer, the request, why it stopped, and the proposed action. Approve or decline in one click.",
  },
  {
    icon: <Mail size={16} />,
    title: "Summary email and CSAT",
    body: "A themed recap after a resolved conversation, with a one-tap rating. It goes to the address already verified on the order — never one supplied mid-chat.",
  },
];

const CONTROLS = [
  {
    icon: <BadgeCheck size={15} />,
    title: "Identity before account data",
    body: "Proven at the tool layer, not merely asked for in a prompt, and remembered for the conversation so nobody is interrogated twice.",
  },
  {
    icon: <ShieldCheck size={15} />,
    title: "Limits the model cannot argue with",
    body: "The refund cap and window live in code. They are never stated in the prompt, so there is nothing to talk the agent out of.",
  },
  {
    icon: <BookOpen size={15} />,
    title: "No source, no claim",
    body: "An answer that cannot be traced to a retrieved passage is withheld, and the customer is offered a person instead.",
  },
  {
    icon: <ScrollText size={15} />,
    title: "A complete audit trail",
    body: "Every sensitive read and write is recorded — including the refusals, which are usually the interesting ones.",
  },
];

export default function FeaturesPage() {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <section className="aura border-b border-line px-5 py-16 sm:py-20">
          <div className="mx-auto max-w-3xl">
            <p className="text-label mb-3 uppercase text-accent">
              The job description
            </p>
            <h1 className="text-title text-fg sm:text-display">
              What your digital employee is responsible for
            </h1>
            <p className="mt-4 max-w-2xl text-pretty text-[15px] leading-relaxed text-muted">
              Six areas of frontline work, the tools it uses to do them, and the
              controls that make it safe to let something autonomous near your
              customers and your money.
            </p>
          </div>
        </section>

        <section className="border-b border-line px-5 py-14">
          <div className="mx-auto grid max-w-5xl gap-3 sm:grid-cols-2">
            {JOBS.map((job) => (
              <div key={job.title} className="panel flex gap-3.5 rounded-2xl p-5">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-raised text-accent-soft">
                  {job.icon}
                </span>
                <div>
                  <h2 className="mb-1 text-[14px] font-medium text-fg">
                    {job.title}
                  </h2>
                  <p className="text-[13px] leading-relaxed text-muted">
                    {job.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* The toolbelt, named. A buyer wants to know exactly what it can reach. */}
        <section className="border-b border-line px-5 py-14">
          <div className="mx-auto max-w-5xl">
            <p className="text-label mb-3 uppercase text-accent">The toolbelt</p>
            <h2 className="text-title text-fg">
              Everything it can touch, and nothing else
            </h2>
            <p className="mb-8 mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">
              The model has no database access. These seven tools are the entire
              surface, every call is logged, and the three marked with a lock
              cannot complete without a person.
            </p>

            <div className="panel overflow-hidden rounded-2xl">
              <div className="h-px hairline" />
              <ul className="divide-y divide-line-soft">
                {TOOLS.map((tool) => (
                  <li
                    key={tool.id}
                    className="flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-center sm:gap-5"
                  >
                    <span className="flex w-44 shrink-0 items-center gap-2 text-[13.5px] font-medium text-fg">
                      {tool.name}
                      {tool.gated && (
                        <Lock size={11} className="text-warn" aria-hidden />
                      )}
                    </span>
                    <span className="text-[13px] leading-relaxed text-muted">
                      {tool.blurb}
                    </span>
                    {tool.gated && (
                      <span className="ml-auto shrink-0 rounded-lg border border-warn/25 bg-warn/[0.08] px-2 py-1 text-[11px] font-medium text-warn">
                        Human-gated
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="border-b border-line bg-surface/30 px-5 py-14">
          <div className="mx-auto max-w-5xl">
            <p className="text-label mb-3 uppercase text-accent">The controls</p>
            <h2 className="mb-8 max-w-2xl text-title text-fg">
              Why it can be trusted with a customer
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {CONTROLS.map((control) => (
                <div key={control.title} className="panel rounded-2xl p-5">
                  <p className="mb-1.5 flex items-center gap-2 text-[14px] font-medium text-fg">
                    <span className="text-accent-soft">{control.icon}</span>
                    {control.title}
                  </p>
                  <p className="text-[13px] leading-relaxed text-muted">
                    {control.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="px-5 py-16">
          <div className="mx-auto flex max-w-2xl flex-col items-center text-center">
            <Mark size={36} className="mb-5" />
            <h2 className="text-title text-fg">
              Easier to believe once you have watched it
            </h2>
            <p className="mt-3 text-[15px] leading-relaxed text-muted">
              Ask it for a refund it should not approve on its own, then flip to
              the seller view and find the decision waiting.
            </p>
            <Link
              href="/demo"
              className="mt-6 inline-flex h-11 items-center rounded-xl bg-accent px-5 text-sm font-medium text-white shadow-[inset_0_1px_0_0_rgb(255_255_255/0.22)] transition hover:bg-accent-soft"
            >
              Try the demo
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
