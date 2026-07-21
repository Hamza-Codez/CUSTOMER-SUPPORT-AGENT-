"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { getRole, isSignedIn, signOut } from "./auth";
import { cn } from "@/lib/utils";

/**
 * Nav for the signed-in user. The Tickets link is hidden from customers —
 * hiding it is courtesy, not security: `GET /tickets` returns 403 to a
 * customer regardless of what the UI shows.
 */
export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState(null);
  const [signedIn, setSignedIn] = useState(false);

  // localStorage is client-only, so read it after mount to keep SSR and the
  // first client render identical.
  useEffect(() => {
    setSignedIn(isSignedIn());
    setRole(getRole());
  }, [pathname]);

  if (!signedIn) return null;

  async function leave() {
    await signOut();
    setSignedIn(false);
    router.replace("/signin");
  }

  return (
    <nav className="flex items-center gap-1 text-sm">
      <NavLink href="/" active={pathname === "/"}>Chat</NavLink>
      {role === "agent" && (
        <NavLink href="/tickets" active={pathname === "/tickets"}>Tickets</NavLink>
      )}
      <button
        onClick={leave}
        title="Sign out"
        aria-label="Sign out"
        className="ml-1 rounded-lg px-2 py-1.5 text-ink-muted transition-colors hover:bg-base-700 hover:text-ink"
      >
        <LogOut className="h-4 w-4" aria-hidden />
      </button>
    </nav>
  );
}

function NavLink({ href, active, children }) {
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
