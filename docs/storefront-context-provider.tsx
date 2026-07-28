"use client";

/**
 * Publishes the storefront's context for the support widget, on every page.
 *
 * Drop this into the root layout once. It keeps `window.fteContext` in step with
 * whatever the customer is looking at, so the agent can answer "where's my
 * order?" from a product page just as well as from the orders page.
 *
 * **Why a component and not a script tag.** A `<script>` in the layout runs once
 * on first load. An App Router navigation does not re-run it, so a widget opened
 * after three client-side transitions would be describing the page the customer
 * arrived on rather than the one they are standing on. A client component with
 * `usePathname` re-publishes on every route change.
 *
 * **Why this is safe to be unsigned.** Everything here is already on the page in
 * front of the customer, so echoing it back to that same browser reveals nothing
 * new. The backend marks it `declared`, which means the agent may discuss it but
 * may never act on it — no refund, no read of the seller's records. If this app
 * later grows a real server-side session, sign the same payload on the server
 * instead and set `window.fteSession`; nothing else has to change.
 *
 * **Never put a secret in here.** This object is readable in devtools by anyone.
 */

import { usePathname } from "next/navigation";
import { useEffect } from "react";

declare global {
  interface Window {
    fteContext?: unknown;
  }
}

/** Whatever your app already calls these. Map, do not rename your own types. */
export type StorefrontContextInput = {
  customerName?: string;
  orders?: Array<{
    id: string;
    status?: string;
    date?: string;
    total?: string | number;
    itemCount?: number;
    carrier?: string;
    trackingNumber?: string;
    eta?: string;
  }>;
  cart?: Array<{ name: string; quantity?: number; price?: string | number }>;
};

export function FteStorefrontContext(props: StorefrontContextInput) {
  const pathname = usePathname();

  // Serialised for the dependency array: the arrays are rebuilt on every render
  // by most data layers, so comparing them by reference would republish on every
  // keystroke, and comparing them not at all would never republish.
  const fingerprint = JSON.stringify(props);

  useEffect(() => {
    const { customerName, orders = [], cart = [] } = JSON.parse(
      fingerprint,
    ) as StorefrontContextInput;

    window.fteContext = {
      customer: customerName ? { name: customerName } : {},
      orders: orders.map((o) => ({
        order_id: o.id,
        status: o.status ?? "",
        placed_at: o.date ?? "",
        total: o.total != null ? String(o.total) : "",
        items: o.itemCount ?? 0,
        carrier: o.carrier ?? "",
        tracking: o.trackingNumber ?? "",
        eta: o.eta ?? "",
      })),
      cart: cart.map((c) => ({
        name: c.name,
        qty: c.quantity ?? 1,
        price: c.price != null ? String(c.price) : "",
      })),
      page: {
        url: pathname,
        title: typeof document !== "undefined" ? document.title : "",
      },
    };

    // Not cleared on unmount. The widget lives outside React's tree and reads
    // this at the moment it opens; blanking it during a route transition would
    // make the rows vanish for whoever opened the panel mid-navigation.
  }, [fingerprint, pathname]);

  return null;
}
