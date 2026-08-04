# THEME.md

How this interface is styled: the tokens, the colour roles, the chat surfaces,
and what the green actually means.

The source of truth is [`app/globals.css`](app/globals.css). This document
explains the reasoning and the conventions that live in component code rather
than in the stylesheet — it does not restate every token. **If the two disagree,
the stylesheet is right and this file is stale.**

One rule underneath everything: **a hex literal in a component is a bug.** Every
shade is a token, so changing the palette is one edit and two screens built weeks
apart still match. The one deliberate exception is the embedded widget, explained
at the end.

Tailwind v4 has no config file. Tokens are declared in `@theme { }` inside
`globals.css`, and Tailwind generates the utilities from them — `--color-ok`
becomes `text-ok`, `border-ok`, `bg-ok/12` and so on automatically.

---

## 1. Surfaces

Four steps, darkest to lightest, so hierarchy is always available without
inventing a shade at the point of use.

| Token | Value | Where it goes |
|---|---|---|
| `ink` | `#08080a` | the page itself (`body`) |
| `surface` | `#0f0f12` | cards, the agent's chat bubble, section bands |
| `raised` | `#16161a` | inputs, chips, anything sitting *on* a card |
| `elevated` | `#1c1c21` | hover states, a disabled button's fill |

Three line tokens separate them: `line` (`#26262c`) is the default border,
`line-soft` (`#1b1b20`) is for the faint background grid, and `line-lit`
(`#34343c`) is the lighter hairline used on the **top edge** of a raised surface
and on hover.

Cards are not "one grey with a border drawn on". The `panel` and `panel-raised`
utilities layer two background images: a radial bloom from the top-right corner
and a 1px linear gradient along the top edge. That top edge catching light is
what makes a dark card read as a physical surface rather than a rectangle. The
bloom sits *above* the edge in layer order, so the edge picks up its colour as it
passes underneath.

---

## 2. Text

| Token | Value | Use |
|---|---|---|
| `fg` | `#fafafa` | headings, the answer itself |
| `body` | `#d6d6db` | paragraphs, list items |
| `muted` | `#9d9da6` | supporting copy, captions |
| `faint` | `#6b6b75` | hints, timestamps, disabled |

Four levels sounds like a lot until you write a card with a title, a description,
a value and a hint in it — which this UI does constantly.

**Type scale.** `display` / `title` / `heading` / `label` are declared as tokens
with their own line-height, tracking and weight, so `text-title` carries all four
and no component sets tracking by hand. Large text is tracked **tight**
(`-0.035em` at display size); the uppercase micro-label is tracked **loose**
(`+0.09em`) or it reads as a smudge. That inversion is the single change that
most separates considered typography from default typography.

**Radius is remapped, and this trips people up.** Every tier is one step tighter
than Tailwind's default of the same name: `rounded-xl` here is **8px**, not 12px;
`rounded-2xl` is 10px. A card at 16px reads as a bubble, and a UI built from
bubbles reads as a template. Change the scale in `@theme`, never the call site.

---

## 3. Colour roles

This is the part worth internalising, because the names do not all mean what they
look like.

### Magenta — *actions*

`--color-magenta: #6b055d`, with `soft` / `deep` / `dim` around it. Every button
that performs an action is filled with it via the `action` utility, so the eye
learns one colour for "this is the move".

The scale runs **downward** from the brand colour rather than upward, because the
lighter a magenta gets the pinker it reads. The fill is a two-stop gradient
(lighter at the top) so it looks like a surface facing up into the light, and the
shadow under it uses a *deeper* magenta than the fill — a glow in the fill's own
brightness is exactly what makes a dark magenta fringe pink.

`action` is a utility rather than a component variant so a marketing-page `<a>`
styled as a CTA and a real `<button>` in the console cannot drift apart.

### Accent — *quiet emphasis*, and it is grey

`--color-accent: #6b6b75`. **The comment above it in `globals.css` says "purple",
which is stale** — the value is a desaturated grey, and `accent-soft` (`#9d9da6`)
is the same value as `muted`. Worth knowing before you reach for `text-accent`
expecting colour: you will get grey.

What accent actually carries: the focus ring, uppercase eyebrow labels, the
`hairline` on accented cards, the ambient `aura` glows behind hero sections, the
chat composer's focus-within border, and the user's own chat bubble.

### The semantic trio

| Token | Value | Meaning |
|---|---|---|
| `ok` | `#34d399` | green — it happened, it is complete, it is valid |
| `warn` | `#fbbf24` | amber — held, pending a human, coming soon |
| `alert` | `#fb7185` | rose — refused, failed, destructive |

---

## 4. Green: what it means, and where it is *not*

Green (`ok`) means **something is confirmed by real state** — never decoration.

Where it appears:

- **Step completion** on `/integrations` — a step turns green because the backend
  reported it done (profile from `/auth/me`, passages from `/dashboard/overview`,
  keys from `/site-keys`), never because the user clicked past it.
- **Selected choices** — scanned pages ticked for import, platform and volume
  chips in the request form.
- **The "Available" flavour badge**, against amber for "Coming soon".
- **Action chips with an `ok` verdict** — see §6.
- **Success messages**, e.g. "Saved 3 passages".

**Green is not the focus ring.** The focus treatment is declared once, globally:

```css
*:focus-visible {
  outline: 2px solid var(--color-accent);   /* grey, not green */
  outline-offset: 2px;
  border-radius: var(--radius-lg);
}
```

One treatment everywhere, so keyboard users get one consistent signal regardless
of what they land on. The chat composer additionally lifts its whole border on
`focus-within:border-accent/50`, because the visible control is the rounded shell
rather than the borderless `<input>` inside it. Both are accent grey.

So: **green = confirmed state, grey = "you are here".** Keeping those apart is
deliberate — if focus were green, a focused-but-incomplete step and a completed
step would look the same.

### Opacity convention

Semantic colours are almost never used at full strength for anything but text and
icons. The convention across the app:

| Layer | Range | Example |
|---|---|---|
| Fill | 6–15% | `bg-ok/12`, `bg-alert/[0.06]` |
| Border | 25–45% | `border-ok/40`, `border-accent/45` |
| Text / icon | 100% | `text-ok` |

A selected item is therefore `border-ok/40 bg-ok/12 text-ok` — readable at a
glance, but never a slab of saturated colour on a dark surface.

---

## 5. Chat: the main conversation

[`components/ChatWidget.tsx`](components/ChatWidget.tsx). The transcript is a
`max-w-2xl` column with `gap-5`, over a composer pinned to the bottom in a
`bg-surface/60 backdrop-blur` bar.

**Bubbles are asymmetric on purpose** — the customer and the agent should never
be mistaken for each other at a glance:

| | Customer | Agent |
|---|---|---|
| Alignment | right, `max-w-[82%]` | left, full width beside a 26px mark |
| Fill | `bg-accent/[0.13]` | `bg-surface` |
| Border | `border-accent/25` | `border-line` |
| Text | `text-fg` | `text-body` |
| Corner | `rounded-2xl rounded-br-md` | `rounded-2xl rounded-tl-md` |

The single squared corner points back at its author. A failed turn keeps the
agent's shape but swaps to `border-alert/30 bg-alert/[0.06] text-alert`, so an
error is visibly still part of the conversation rather than a banner bolted on
top.

Every message enters with `animate-rise` — 8px up, 0.28s, on a
`cubic-bezier(0.22, 1, 0.36, 1)` ease-out.

### The waiting state

`Working()` is the most opinionated piece of styling here, and it is shaped by an
honesty constraint: the backend answers a turn in **one** response rather than
streaming its steps, so the indicator must not claim to know which tool is
running right now.

It shows three `typing-dot` dots (staggered 0.16s), a rotating label from
`WORKING_STAGES`, and a 1px rail with a light sweeping along it
(`animate-sweep`). After the four stages run out it switches to a **live second
counter**, and past 20s it says it may be starting up or rate-limited.

That last part is a fix, not a flourish. The previous version clamped at
"Composing a reply…" and sat there indefinitely, which made a slow turn
indistinguishable from a hang. Counting seconds is less reassuring and more true.

---

## 6. Action chips — colour driven by outcome

[`components/ActionChips.tsx`](components/ActionChips.tsx) renders what the agent
actually did, under its reply. **A chip cannot appear unless the backend emitted
the action**, and the colour comes from `verdictFor()` in
[`lib/tools.ts`](lib/tools.ts) — one mapping, so the chips and the tool rack can
never disagree.

| Verdict | Classes | Meaning | Example kinds |
|---|---|---|---|
| `ok` | `border-ok/25 bg-ok/[0.08] text-ok` | it worked | `order_looked_up`, `policy_cited`, `refund_executed`, `email_sent` |
| `held` | `border-warn/25 bg-warn/[0.08] text-warn` | stopped on purpose | `approval_pending`, `escalated`, `no_policy_match`, `order_not_found` |
| `blocked` | `border-alert/25 bg-alert/[0.08] text-alert` | refused or failed | `identity_check_failed`, `refund_refused`, `email_failed` |
| `neutral` | `border-line bg-raised text-muted` | it happened, no verdict | `routed`, `greeted`, `refund_duplicate` |

The distinction between **held** and **blocked** is the one that matters: a
refusal is not a failure. `no_policy_match` is amber because retrieval correctly
returning nothing is the system working — colouring it red would train sellers to
read correct behaviour as breakage.

Chips reveal in sequence with a 90ms stagger, because the tools genuinely ran in
that order. The animation is showing real events, not dressing up one response.

---

## 7. Motion

Four keyframes, all short and all ease-out: `rise` (messages, 0.28s), `slide-in`
(chips and label changes, 0.24s), `pulse-dot` (typing, 1.2s loop), `sweep`
(progress rail, 1.4s loop). There is also `working` — a breathing ring for a tool
that is currently running, deliberately *not* a spinner, because a spinner says
"waiting" and this should say "working".

The whole system is disabled under `prefers-reduced-motion: reduce`, which clamps
every animation and transition to 0.01ms globally.

---

## 8. The embedded widget is a separate stylesheet, and that is intentional

[`backend/app/comms/widget.py`](../backend/app/comms/widget.py) serves
`widget.js`, which renders into a **shadow root** on the seller's own storefront.
It therefore cannot use Tailwind or any token from `globals.css` — it must ship
its own CSS as a string, inside a boundary that stops it inheriting the store's
styles or leaking its own.

It mirrors the palette by hand: `#0f0f12` panel, `#26262c` borders, `#16161a`
raised, `#d6d6db` body, `#fb7185` errors, and the same asymmetric bubbles
(customer right in translucent magenta, agent left on `#16161a`).

**Two divergences to know about, both real:**

1. **The magenta differs.** The widget fills its launcher and send button with
   `#870775`, while the app's `--color-magenta` is `#6b055d`. `#870775` does
   appear in `globals.css`, but only inside `--shadow-glow` — it is not the fill
   colour anywhere in the app. The widget is therefore a visibly brighter
   magenta than the product it belongs to.
2. **Its chips are monochrome.** The embedded widget renders every chip as
   `#26262c` border / `#9d9da6` text with no verdict colouring, so the ok / held
   / blocked distinction from §6 is lost on the storefront.

Neither is load-bearing, but both mean the widget and the dashboard do not
currently look like the same product. Fixing #1 is a one-line change; #2 needs
`verdictFor`'s mapping duplicated into the widget script.

---

## 9. Conventions for new work

- Reach for a token, never a hex. If no token fits, add one to `@theme` — that
  is the decision point, not the component.
- Selection and completion are **green**; focus is **accent grey**. Do not merge
  them.
- Amber for anything held, pending or not yet available. Red only for refused,
  failed or destructive.
- Fills 6–15%, borders 25–45%, text at full strength.
- Give every data view a loading, empty and error state. Error copy says what
  broke *and* what to do — an unreachable backend prints the command to start it.
- Anything that claims something happened must be bound to a real API result. The
  audit's central charge was that the UI displayed strings the agent never
  produced; a green tick that is not read back from the backend is that same bug
  wearing a new colour.

---

## Not verified

**How any of this looks in a browser.** There is no browser in this environment,
so nothing in this document has been seen rendered. It describes the CSS that is
in the repo and builds cleanly (`npm run build`, `npx eslint .`) — not a visual
result anyone has confirmed.
