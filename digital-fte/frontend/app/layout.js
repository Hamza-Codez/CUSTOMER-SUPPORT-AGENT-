import Link from "next/link";
import "./globals.css";
import { NavLink } from "./nav-link";

export const metadata = {
  title: "Digital FTE — Support Agent",
  description: "AI Customer Support Agent",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="sticky top-0 z-10 border-b border-base-line bg-base-900/85 backdrop-blur">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-6 px-6 py-3">
            <Link href="/" className="flex items-center gap-2.5 rounded-lg">
              <span
                className="grid h-7 w-7 place-items-center rounded-lg bg-accent-600 text-xs font-bold text-white"
                aria-hidden
              >
                FTE
              </span>
              <span className="text-sm font-semibold tracking-tight">Support Agent</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <NavLink href="/">Chat</NavLink>
              <NavLink href="/tickets">Tickets</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
