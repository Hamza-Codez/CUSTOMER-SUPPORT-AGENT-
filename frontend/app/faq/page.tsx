import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { brand } from "@/lib/brand";

export const metadata: Metadata = {
  title: "FAQ",
  description: `Common questions about ${brand.name}: how it avoids inventing answers, what it can and cannot do without a human, how refunds are capped, what data it reads, and how it is embedded on your store.`,
};

/* Answers are specific on purpose. "Enterprise-grade security" tells a buyer
 * nothing; "the cap lives in code and is never stated in the prompt" is a claim
 * they can check. */
const SECTIONS: { heading: string; items: { q: string; a: string }[] }[] = [
  {
    heading: "How it behaves",
    items: [
      {
        q: "Can it make up an answer?",
        a: "It can only cite passages retrieved from your own documents, and retrieval returns nothing when your documents don't cover the question. When that happens it says it can't confirm and offers a colleague. An answer that can't be traced to a passage is withheld before the customer ever sees it.",
      },
      {
        q: "What stops it from telling the wrong person about an order?",
        a: "Nothing about an account is revealed until the order number and the email on that order match. The check happens in the tool that reads the database, not in the prompt, so there is no wording that talks past it. A failed check is recorded in the audit log.",
      },
      {
        q: "What if a customer tries to manipulate it?",
        a: "Obvious attempts — instruction overrides, 'admin mode', asking it to skip verification — are screened before any agent runs. Past that, the defences are structural: the tenant, the verified order and the email recipient all come from your data rather than from anything the customer typed, so there is no phrasing that redirects them.",
      },
      {
        q: "Does it handle a customer who is angry?",
        a: "It acknowledges first and escalates rather than arguing. Emotional or high-stakes conversations are a reason to involve a person, not an edge case to survive.",
      },
    ],
  },
  {
    heading: "Money and control",
    items: [
      {
        q: "Can it issue refunds on its own?",
        a: "Small, recent, in-policy ones, yes. Anything above your automatic limit, outside your refund window, or on an order that hasn't been delivered stops and waits for you. The limit and the window live in code and are never written into the prompt, so there is nothing for the model to be argued out of.",
      },
      {
        q: "What do I actually see when it stops?",
        a: "A Decision Card: the verified customer, what they asked for, why it stopped, the exact proposed action, and Approve or Decline. Approving resumes the original paused conversation rather than starting a new one, so the customer gets the outcome in the same thread.",
      },
      {
        q: "Could it refund the same order twice?",
        a: "No. One refund per order is enforced by a database constraint, not by the agent remembering. A retried request, a duplicated click or two operators approving at once all collide there, and only one succeeds.",
      },
      {
        q: "What happens if I decline?",
        a: "The customer is told, with the reason you gave, in the same conversation. Nothing moves.",
      },
    ],
  },
  {
    heading: "Your data",
    items: [
      {
        q: "What does it read?",
        a: "Only what a defined tool returns: an order, a product, a policy passage. It has no direct database access, and tools return the specific fields needed rather than whole rows — so customer email and address never reach the model at all.",
      },
      {
        q: "Is my store's data separated from other stores?",
        a: "Every record carries a tenant key, and that key comes from your session rather than from anything the model or the customer supplies. A brand-new account sees an entirely empty store.",
      },
      {
        q: "Can I see what it did?",
        a: "Every sensitive read and write is logged with who, what, when and the outcome — including the refusals, which are usually the more interesting entries.",
      },
    ],
  },
  {
    heading: "Setting it up",
    items: [
      {
        q: "How long does setup take?",
        a: "Paste your policies at sign-up and it can answer immediately. Embedding it on your storefront is a script tag; connecting your real orders is the part that takes a conversation, because it depends on your platform.",
      },
      {
        q: "Do my customers need an account?",
        a: "No. The widget lives on your site and identifies people by order number and email. Accounts here are for you and your team.",
      },
      {
        q: "What if it gets something wrong?",
        a: "Escalate it from the operator queue and the conversation goes to a person with full context. If it answered from a policy that was wrong, edit the document — the agent's answers change with it, because it reads your documents rather than a copy of them.",
      },
    ],
  },
];

export default function FaqPage() {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <section className="aura border-b border-line px-5 py-16 sm:py-20">
          <div className="mx-auto max-w-3xl">
            <p className="text-label mb-3 uppercase text-accent">FAQ</p>
            <h1 className="text-title text-fg sm:text-display">
              The questions worth asking
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
              Mostly about what it will refuse to do. That is the part that
              decides whether something autonomous belongs near your customers.
            </p>
          </div>
        </section>

        <section className="px-5 py-14">
          <div className="mx-auto flex max-w-3xl flex-col gap-12">
            {SECTIONS.map((section) => (
              <div key={section.heading}>
                <h2 className="mb-5 text-heading text-fg">{section.heading}</h2>
                <div className="flex flex-col gap-2.5">
                  {section.items.map((item) => (
                    <details
                      key={item.q}
                      className="group panel rounded-2xl px-5 py-4 transition"
                    >
                      <summary className="flex cursor-pointer list-none items-center gap-3 text-[14px] font-medium text-fg marker:hidden">
                        <span className="flex-1">{item.q}</span>
                        <span className="shrink-0 text-faint transition group-open:rotate-45">
                          +
                        </span>
                      </summary>
                      <p className="mt-3 border-t border-line-soft pt-3 text-[13.5px] leading-relaxed text-muted">
                        {item.a}
                      </p>
                    </details>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border-t border-line px-5 py-16">
          <div className="mx-auto max-w-xl text-center">
            <h2 className="text-heading text-fg">Still deciding?</h2>
            <p className="mx-auto mt-2.5 max-w-md text-[14.5px] leading-relaxed text-muted">
              The demo answers most of this faster than reading about it. Ask for
              a refund it shouldn&apos;t approve and watch what it does.
            </p>
            <Link
              href="/demo"
              className="action mt-6 inline-flex h-11 items-center rounded-xl px-5 text-sm font-medium transition active:translate-y-px"
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
