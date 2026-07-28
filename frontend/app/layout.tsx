import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { brand } from "@/lib/brand";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(`https://${brand.domain}`),
  title: {
    default: `${brand.name} — ${brand.tagline}`,
    template: `%s · ${brand.name}`,
  },
  description: brand.promise,
  keywords: [
    "AI customer support agent",
    "ecommerce support automation",
    "AI order tracking",
    "human in the loop refunds",
    "AI customer service for online stores",
  ],
  openGraph: {
    type: "website",
    title: `${brand.name} — ${brand.tagline}`,
    description:
      "Grounded in your real records and your own policies. Routine work handled, risky calls prepared for a human.",
    siteName: brand.name,
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
