# Digital FTE — Frontend

Next.js 16 (App Router, Turbopack) · React 19 · Tailwind v4 · TypeScript.

The marketing pages are static and indexable; the dashboard is client-side
because the API token lives in the browser.

---

## Run it

The backend needs to be up first — the dashboard is a view onto it.

```bash
# terminal 1
cd backend && uv run uvicorn app.main:app --reload

# terminal 2
cd frontend
cp .env.local.example .env.local     # NEXT_PUBLIC_API_URL
npm install
npm run dev                          # http://localhost:3000
```

Open `/login`, pick **Customer**, ask for a refund on `ORD-1001`
(`ayesha.k@example.com`) — it will stop short and say a colleague is reviewing
it. Flip the toggle to **Seller** and the Decision Card is already waiting.

`ORD-1005` is under the auto-cap and refunds immediately, for the contrast.

## Routes

| Route | Rendering | Purpose |
|---|---|---|
| `/` | static | The pitch — hero plus five sections |
| `/features` | static | The FTE's job description and its controls |
| `/pricing` | static | Core vs Pro comparison |
| `/login` | client | Role gateway into the demo |
| `/dashboard` | client, gated | The dual customer/seller dashboard |
| `/demo` | client | The guided playground — the ten-step tour |

## Layout

```
app/
  layout.tsx        fonts + site-wide metadata
  globals.css       THE DESIGN TOKENS — purple/black/zinc, defined once
  page.tsx          landing
  features/ pricing/ login/ dashboard/
components/
  ChatWidget.tsx        chat surface: bubbles, quick replies, typing, errors
  ActionChips.tsx       what the agent actually did, under its reply
  SellerView.tsx        escalation queue + CSAT, polled
  DecisionCardView.tsx  the one-click approve/decline card
  SiteChrome.tsx        marketing header/footer (server components)
  demo/steps.ts         the ten steps, their copy and what each one does
  demo/OpsPeek.tsx      step 9 — records, stock, policies, audit log
  demo/EmailPreviewPanel.tsx  step 8 — the real summary email, sandboxed
  ui/primitives.tsx     Button, Card, Badge, Input, Skeleton, Empty, Error
lib/
  api.ts            the single door to the backend
  types.ts          mirrors the backend's Pydantic contracts
```

### What the design commits to

- **Tokens, not ad-hoc colour.** Every shade is a token in `globals.css`. A
  component with a hex literal in it is a bug — changing the palette should be
  one edit, and two screens built weeks apart should still match.
- **Dark by choice, not by toggle.** It is an operations console; committing to
  one treatment is what stops it reading as default shadcn.
- **The agent's work is visible.** Action chips under every reply are built from
  real tool results, so a chip cannot appear unless the thing it names happened.
- **Loading, empty and error on every data view.** The error states say what
  broke and what to do — an unreachable backend prints the command to start it.
- **The ModeToggle is top-level** and persists, because flipping between the two
  sides is the point of the product rather than a settings preference.

## Verified

- `npm run build` — clean, all seven routes prerendered, TypeScript passes.
- **The demo tour's exact API sequence replayed against the live backend**: all
  ten steps produce their expected outcome, including the identity gate
  withholding data, the small refund executing, the large one pausing, approval
  resuming the original run, and the summary email rendering with its feedback
  link.
- `npx eslint .` — no errors.
- Every route serves 200 from `next start`, with correct `<title>` and
  description in the server-rendered HTML.
- CORS preflight from `http://localhost:3000` is accepted by the backend for
  `POST /chat` with an `Authorization` header.
- The exact calls this UI makes return the expected shapes against the live
  backend on PostgreSQL: a refund request pauses, and the Decision Card comes
  back with `verified: true`.

**Not verified: how it looks and behaves in a browser.** There is no browser in
this environment, so the visual result, the click-through, and the responsive
behaviour have not been seen — only that the pages build, serve, and are wired
to endpoints that answer correctly.

## Known gaps

- **`/login` is a token screen, not sign-up.** The backend has no `/auth/signup`
  or `/auth/login`; it authenticates with static `DEV_TOKENS`. A password form
  here would post nowhere, so the page offers the two demo roles instead.
- **No side-by-side product compare card.** `/chat` returns the compared product
  *names* in an action chip but not their attributes, so a real comparison table
  would need a products endpoint on the backend rather than invented detail.
- **No streaming.** `POST /chat` is request/response today; the typing indicator
  is honest about waiting rather than faking token-by-token output.
- **The demo holds both demo tokens.** Seeing both sides in one tab is the
  point of the tour, and signing in and out halfway through would break it. They
  are the public seed-data tokens; the backend still authenticates every call.
