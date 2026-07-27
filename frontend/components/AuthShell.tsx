import Link from "next/link";

import { Wordmark } from "@/components/Brand";

/** Shared frame for sign-up and sign-in.
 *
 * Two columns: the form, and a reason to fill it in. A bare form on an empty
 * page is where most products lose people who were only half convinced. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  aside,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <main className="grid min-h-dvh lg:grid-cols-[1fr_26rem]">
      <div className="aura flex flex-col justify-center px-5 py-14 sm:px-10">
        <div className="mx-auto w-full max-w-sm">
          <Wordmark className="mb-9" />
          <h1 className="text-title text-fg">{title}</h1>
          <p className="mb-8 mt-2 text-[14px] leading-relaxed text-muted">
            {subtitle}
          </p>
          {children}
          <div className="mt-6 text-[13px] text-faint">{footer}</div>
        </div>
      </div>

      <aside className="hidden flex-col justify-center border-l border-line bg-surface/40 px-9 lg:flex">
        {aside}
      </aside>
    </main>
  );
}

export function AuthAside({
  heading,
  points,
}: {
  heading: string;
  points: { title: string; body: string }[];
}) {
  return (
    <div className="max-w-xs">
      <h2 className="mb-6 text-[15px] font-semibold text-fg">{heading}</h2>
      <ul className="flex flex-col gap-5">
        {points.map((point) => (
          <li key={point.title} className="flex gap-3">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            <span>
              <span className="block text-[13px] font-medium text-body">
                {point.title}
              </span>
              <span className="mt-0.5 block text-[12.5px] leading-relaxed text-faint">
                {point.body}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-8 border-t border-line-soft pt-5 text-[12px] leading-relaxed text-faint">
        Prefer to look first?{" "}
        <Link href="/demo" className="text-accent-soft hover:underline">
          Try the demo
        </Link>{" "}
        — no account needed.
      </p>
    </div>
  );
}
