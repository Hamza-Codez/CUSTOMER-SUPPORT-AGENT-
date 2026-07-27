import Link from "next/link";

/** Shared header and footer for the marketing pages. Server components — these
 * pages are static and want to stay indexable. */

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-ink/80 backdrop-blur">
      <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3.5 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15 text-[13px] font-bold text-accent">
            F
          </span>
          <span className="text-sm font-semibold text-fg">Digital FTE</span>
        </Link>
        <div className="ml-auto flex items-center gap-1 text-[13px] sm:gap-5">
          <Link
            href="/features"
            className="hidden px-2 py-1 text-muted transition hover:text-fg sm:block"
          >
            Features
          </Link>
          <Link
            href="/pricing"
            className="hidden px-2 py-1 text-muted transition hover:text-fg sm:block"
          >
            Pricing
          </Link>
          <Link
            href="/demo"
            className="rounded-xl bg-accent px-3.5 py-2 text-[13px] font-medium text-white transition hover:bg-accent-soft"
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
    <footer className="border-t border-line px-4 py-10 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 text-[12px] text-faint sm:flex-row sm:items-center">
        <p>Digital FTE — frontline support that does the job.</p>
        <div className="flex gap-4 sm:ml-auto">
          <Link href="/features" className="transition hover:text-body">
            Features
          </Link>
          <Link href="/pricing" className="transition hover:text-body">
            Pricing
          </Link>
          <Link href="/demo" className="transition hover:text-body">
            Demo
          </Link>
        </div>
      </div>
    </footer>
  );
}
