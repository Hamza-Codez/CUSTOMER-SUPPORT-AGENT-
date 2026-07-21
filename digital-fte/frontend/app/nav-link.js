"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

/** Nav item that knows whether it's the current page. */
export function NavLink({ href, children }) {
  const pathname = usePathname();
  const active = pathname === href;

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "rounded-lg px-3 py-1.5 transition-colors",
        active ? "bg-base-700 text-ink" : "text-ink-muted hover:text-ink"
      )}
    >
      {children}
    </Link>
  );
}
