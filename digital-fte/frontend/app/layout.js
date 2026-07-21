import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "Digital FTE — Support Agent",
  description: "AI Customer Support Agent",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <span className="brand">🤖 Digital FTE</span>
          <nav>
            <Link href="/">Chat</Link>
            <Link href="/tickets">Tickets</Link>
          </nav>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
