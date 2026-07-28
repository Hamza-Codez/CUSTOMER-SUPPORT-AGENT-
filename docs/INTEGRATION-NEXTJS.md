# Putting the agent on a Next.js storefront

For a storefront where the customer is already signed in — so the widget opens
knowing who they are, lists their orders as tappable rows, and never asks for an
order number or an email address.

Every command below was run against a live server before this was written. Where
something is expected rather than measured, it says so.

---

## What changed, and why you need a new key

Site keys now carry a **signing secret**. Your storefront's server uses it to
vouch for the logged-in customer, which is what removes the interrogation.

**A key minted before this has an empty secret and cannot sign anything.** Create
a new one. Everything below assumes you have.

---

## The trust model, in one table

Read this before the steps; it explains why step 3 exists at all.

| Grade | Where it comes from | What the agent may do with it |
|---|---|---|
| **attested** | your server signs it with the key's secret | proves identity; can ground a refund |
| **declared** | your page hands it over unsigned | quoted back and shown as rows; **cannot** read our records, **cannot** move money |

The page is client-controlled, so anything the browser hands us the browser can
forge. Declared context is still useful — a storefront with no backend gets the
whole experience — and it is safe precisely because everything it touches goes
straight back to the browser that supplied it.

A **bad signature is dropped, not downgraded**. Signing with the wrong secret
gets you nothing, not "declared".

---

## Step 1 — Create the key and read its secret

Integrations → **Embedded widget** → sign in → enter your storefront address →
**Create key**.

> **Include the scheme.** Typing `localhost:3000` stores `https://localhost:3000`,
> which will never match a browser sending `http://`. Measured: it returns 403.
> Type `http://localhost:3000`.

Then read the secret (operator token, your own key only):

```bash
curl -s http://localhost:8000/site-keys/pk_YOUR_KEY/secret \
  -H "Authorization: Bearer YOUR_OPERATOR_TOKEN"
# {"key":"pk_...","secret":"sk_..."}
```

**Verify:** you get a `sk_` string ~46 characters long. A 404 means the key
belongs to a different account than the token — keys are tenant-scoped.

---

## Step 2 — Environment

```bash
# .env.local  — NEXT_PUBLIC_ values reach the browser; the secret must not.
NEXT_PUBLIC_FTE_API=http://localhost:8000
NEXT_PUBLIC_FTE_KEY=pk_your_public_key
FTE_SECRET=sk_your_signing_secret
```

**Verify:** `grep FTE_SECRET` finds it only in `.env.local` and your route
handler. If `sk_` ever appears in a `NEXT_PUBLIC_` variable or in browser
output, stop — that secret is now public and must be revoked.

---

## Step 3 — A route handler that signs the assertion

No dependencies: `node:crypto` produces the HS256 JWT directly.

**Verified:** a token from exactly this code was accepted by the backend
(customer, orders, tracking, ETA and cart all intact) and rejected as
`invalid signature` under a different secret.

```ts
// app/api/fte-session/route.ts
import crypto from "node:crypto";
import { NextResponse } from "next/server";

const b64 = (s: string) => Buffer.from(s).toString("base64url");

function sign(secret: string, payload: object, ttl = 900) {
  const now = Math.floor(Date.now() / 1000);
  const head = b64(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64(JSON.stringify({ ...payload, iat: now, exp: now + ttl }));
  const sig = crypto
    .createHmac("sha256", secret)
    .update(`${head}.${body}`)
    .digest("base64url");
  return `${head}.${body}.${sig}`;
}

export async function GET() {
  // Replace with your real session lookup. Whatever you put here is what the
  // agent will treat as proven, so it must come from your auth — never from a
  // query string or a header the browser controls.
  const customer = await getSignedInCustomer();
  if (!customer) return NextResponse.json({ token: null });

  const token = sign(process.env.FTE_SECRET!, {
    customer: { ref: customer.id, name: customer.name, email: customer.email },
    orders: customer.orders.map((o) => ({
      order_id: o.id,
      status: o.status,          // free text; "out for delivery" is fine
      placed_at: o.date,
      total: o.total,
      items: o.itemCount,
      carrier: o.carrier,
      tracking: o.trackingNumber,
      eta: o.eta,
    })),
    cart: customer.cart.map((c) => ({
      name: c.name,
      qty: c.quantity,
      price: c.price,
    })),
    page: { url: "/orders", title: "Your orders" },
  });

  // No caching: it is per-customer and short-lived.
  return NextResponse.json({ token }, { headers: { "Cache-Control": "no-store" } });
}
```

**Verify:**

```bash
curl -s http://localhost:3000/api/fte-session
# {"token":"eyJhbGciOiJIUzI1NiIs..."}
```

Three segments separated by dots, ~600+ characters. Paste the middle segment
into any base64url decoder — you should see your own customer and orders. It is
signed, not encrypted; that is expected, and it is why nothing secret goes in it.

---

## Step 4 — Hand the token to the widget

```tsx
// app/layout.tsx
import Script from "next/script";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}

        {/* Fetch the assertion, publish it, then load the widget. The widget
            reads window.fteSession at the moment it opens rather than at load,
            so arriving late is fine — but before the first click is better. */}
        <Script id="fte-session" strategy="afterInteractive">
          {`fetch("/api/fte-session")
              .then(r => r.json())
              .then(d => { if (d.token) window.fteSession = d.token; })
              .catch(() => {});`}
        </Script>

        <Script
          src={`${process.env.NEXT_PUBLIC_FTE_API}/widget.js`}
          data-fte-key={process.env.NEXT_PUBLIC_FTE_KEY}
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
```

`afterInteractive` matters — the widget needs `document.body`. `next/script`
injects the tag, which makes `document.currentScript` null; the widget falls back
to scanning for `data-fte-key`, so it still finds its key.

### No backend? Declared mode

Skip step 3 and publish the context unsigned:

```tsx
<Script id="fte-context" strategy="afterInteractive">
  {`window.fteContext = ${JSON.stringify({
    customer: { name: "Robin" },
    orders: [{ order_id: "JC-20260728-8VVK", status: "in_transit", total: "$666.85" }],
    cart: [{ name: "Ceramic Kettle", qty: 1, price: "$89.00" }],
  })};`}
</Script>
```

Same rows, same greeting, and the agent says out loud that it is reading from the
page. Nothing declared can be refunded.

---

## Step 5 — Verify it manually

Work down this list. Each step tells you what a pass looks like and what the
failure means.

### 5.1 The script is served

```bash
curl -sI http://localhost:8000/widget.js | head -3
```

**Pass:** `200`, `content-type: application/javascript`.
**Fail:** connection refused → the backend is not running.

### 5.2 The key works from your origin

```bash
curl -s http://localhost:8000/widget/session \
  -H "X-FTE-Site-Key: pk_YOUR_KEY" \
  -H "Origin: http://localhost:3000"
```

**Pass:** `{"business_name":"Joycart","verified":false,"orders":[],...}` —
anonymous, which is correct with no token.
**403:** the origin on the key does not match. The message names the origin it
actually saw.
**401 "revoked":** the key in your page was revoked; use a live one.
**401 "Unknown":** the key does not exist on the account you are signed in as.

### 5.3 The assertion is accepted

```bash
TOKEN=$(curl -s http://localhost:3000/api/fte-session | python -c "import json,sys;print(json.load(sys.stdin)['token'])")

curl -s http://localhost:8000/widget/session \
  -H "X-FTE-Site-Key: pk_YOUR_KEY" \
  -H "X-FTE-Customer-Session: $TOKEN" \
  -H "Origin: http://localhost:3000"
```

**Pass:** `"verified": true`, your customer's name, your orders, your cart.
**`verified: false` with an empty list:** the signature did not check out —
almost always `FTE_SECRET` not matching the key you are sending. This is the
designed behaviour: a bad signature proves nothing rather than degrading.

### 5.4 The conversation reflects it

```bash
curl -s -X POST http://localhost:8000/chat/public \
  -H "Content-Type: application/json" \
  -H "X-FTE-Site-Key: pk_YOUR_KEY" \
  -H "X-FTE-Customer-Session: $TOKEN" \
  -H "Origin: http://localhost:3000" \
  -d '{"message":"where is my order?","session_id":"manual-1"}'
```

**Pass:** greeted by first name, orders named, and an action chip reading
`Recognised you · N order(s)`. The words "order number" and "email" do not
appear.
**Asks for an order number:** the token was not accepted — go back to 5.3.

### 5.5 In the browser

Open your storefront, click **Support**.

- **Header** shows *your* store name, not "Aeron Home Goods".
- **First message** greets by name, followed by tappable order rows — solid
  border for orders, dashed and purple for basket items.
- **DevTools → Network:** `/widget/session` carries `X-FTE-Customer-Session`.
- **Click an order row** → it sends "About my order …" and answers from that
  order.

**Widget never appears:** check the console. A strict content-security policy on
your site will block a third-party script; you would need to allow the API origin
in `script-src` and `connect-src`.

### 5.6 The one that proves it isn't trusting the page

This is the test worth doing, because it is the difference between a real
integration and a convincing one.

In DevTools, before opening the widget:

```js
window.fteSession = null;
window.fteContext = {
  customer: { name: "Someone Else" },
  orders: [{ order_id: "ORD-1001", status: "delivered", total: "149.00" }],
};
```

Open the widget and ask for a refund on that order.

**Pass:** it will discuss the order — the page already showed it to you — but the
reply says a colleague is involved, and **no refund is executed**. Check the
operator dashboard: nothing was paid.
**Fail:** if money moved, stop and tell me. That would be the bug this whole
design exists to prevent.

---

## What this does not do

- **It does not read your database.** The orders the agent knows are the ones
  your assertion described, plus any you have in the FTE store. The Joycart
  tenant currently has 2 policies, 0 orders and 0 products, so unattested order
  questions correctly return nothing.
- **A refund on an order only your system holds is escalated, not executed.** We
  have no payment record to refund against, so it goes to a person. That is a
  deliberate refusal, not a gap.
- **Nobody has watched this render.** There is no browser in the environment it
  was built in. The endpoints, the signing, the refusals and the script's syntax
  are all verified; the visual behaviour of step 5.5 is yours to confirm.
