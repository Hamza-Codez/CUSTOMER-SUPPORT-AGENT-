import Link from "next/link";

import { Wordmark } from "@/components/Brand";
import { brand } from "@/lib/brand";

const NAV = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/faq", label: "FAQ" },
  { href: "/integrations", label: "Integrations" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-ink/80 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3.5">
        <Wordmark />

        <div className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-1.5 text-[13px] text-muted transition hover:bg-raised hover:text-fg"
            >
              {item.label}
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Link
            href="/login"
            className="hidden rounded-lg px-3 py-1.5 text-[13px] text-muted transition hover:text-fg sm:block"
          >
            Sign in
          </Link>
          <Link
            href="/demo"
            className="rounded-xl bg-accent px-3.5 py-2 text-[13px] font-medium text-white shadow-[inset_0_1px_0_0_rgb(255_255_255/0.22)] transition hover:bg-accent-soft active:translate-y-px"
          >
            Try the demo
          </Link>
        </div>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line px-5 py-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 sm:flex-row">
        <div className="max-w-xs">
          <Wordmark className="mb-3" />
          <p className="text-[12.5px] leading-relaxed text-faint">
            {brand.tagline}. Grounded in your records, and stopping short of every
            decision that should be yours.
          </p>
        </div>

        <div className="grid flex-1 grid-cols-2 gap-8 sm:grid-cols-3 sm:justify-items-end">
          <FooterColumn
            title="Product"
            links={[
              { href: "/features", label: "Features" },
              { href: "/pricing", label: "Pricing" },
              { href: "/demo", label: "Demo" },
            ]}
          />
          <FooterColumn
            title="Get started"
            links={[
              { href: "/signup", label: "Create an account" },
              { href: "/login", label: "Sign in" },
              { href: "/integrations", label: "Integrations" },
            ]}
          />
          <FooterColumn title="Learn" links={[{ href: "/faq", label: "FAQ" }]} />
        </div>
      </div>

      <div className="mx-auto mt-10 max-w-6xl border-t border-line-soft pt-6">
        <p className="text-[12px] text-faint">
          {brand.name} — {brand.tagline}.
        </p>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string }[];
}) {
  return (
    <div>
      <p className="text-label mb-3 uppercase text-faint">{title}</p>
      <ul className="flex flex-col gap-2">
        {links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              className="text-[12.5px] text-muted transition hover:text-fg"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
