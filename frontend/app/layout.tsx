import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://digital-fte.example.com"),
  title: {
    default: "Digital FTE — an AI employee for your storefront",
    template: "%s · Digital FTE",
  },
  description:
    "Hire a digital full-time employee for e-commerce support. It reads your real orders and your own written policies, resolves what it can, and hands money-moving decisions to a human with one click.",
  keywords: [
    "AI customer support agent",
    "ecommerce support automation",
    "AI order tracking",
    "human in the loop refunds",
    "AI customer service for online stores",
  ],
  openGraph: {
    type: "website",
    title: "Digital FTE — an AI employee for your storefront",
    description:
      "Grounded in your real records and your own policies. Routine work handled, risky calls prepared for a human.",
    siteName: "Digital FTE",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
