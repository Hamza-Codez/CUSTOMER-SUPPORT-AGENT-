---
name: frontend-tailwind-shadcn
description: Build the Next.js frontend for the Digital FTE using Tailwind and shadcn/ui with distinctive, non-generic, AI-native UI/UX in the platform's purple/black/zinc theme. Use when the user asks to build or edit the chat UI, dual dashboard, escalation queue, pricing page, demo playground, or any page/component, to style with Tailwind or shadcn, to improve the look/feel, or to make the interface feel polished and not template-like. Covers component structure, design tokens, chat and agent-status patterns, the customer/seller toggle, Decision Cards, accessibility, and states (loading, empty, error).
---

# Frontend: Tailwind + shadcn (AI-native, non-generic)

Ship an interface that looks intentional, not scaffolded. Default shadcn is a
starting point, not the finish. Every screen handles loading, empty, and error
states, and makes the agent's actions visible. Next.js App Router; SSR the
marketing pages for SEO/GEO/AEO.

## Design principles
1. **Not generic.** Commit to the spec theme: **purple / black / zinc** in a refined, minimalist gradient. One radius scale, one font pairing. Avoid the default gray-on-white shadcn look.
2. **AI-native.** Show the agent working: streaming text, action chips ("Refund prepared", "Escalated", "Order looked up"), and a live audit/escalation view. The UI proves it's an agent, not a form.
3. **State-complete.** No screen ships without loading, empty, and error states.
4. **Dual by design.** The customer↔seller `ModeToggle` is a first-class pattern, not an afterthought — it's the emotional centre of the demo and the dashboard.
5. **Calm hierarchy.** One primary action per view. Muted secondary text. Generous spacing over dense borders.
6. **Accessible by default.** Keyboard send, focus rings, aria labels, sufficient contrast (mind contrast on dark purple/zinc).

## Instructions
### Frontend Design Rulings — Apple-Inspired Premium Theme

#### Visual Language & Styling
- Build entirely with **Tailwind CSS** — utility classes drive styling, spacing, and responsive behavior throughout; no ad-hoc inline styles.
- Draw core visual inspiration from **Apple.com**: restrained typography, generous whitespace, purposeful motion, and confident negative space over decoration.
- Avoid generic, overly-rounded "bubbly" buttons or default UI-kit visuals — the aesthetic should feel precise, curated, and premium, never templated.
- Use a **tiered corner-radius system** for hierarchy: cards stay squarish with minimal or no border; buttons use a defined radius scale (`rounded-xl` for primary CTAs, `rounded-lg` for secondary, `rounded-md` for compact/inline actions). Let spacing, shadow, and contrast define edges rather than heavy borders.

#### Color & Gradients
- **Hero and Pricing sections** run a dark theme built from **black, magenta, and gray** — layered as smooth, multi-stop gradients rather than flat two-tone transitions, for a polished, "pro studio" feel.
- Gradients should feel deliberate: soft diagonal or radial blends, gentle light bleed at the edges, no harsh banding or oversaturation.
- Keep color and contrast consistent across every surface — cards, chat interface, navigation, and footer should read as one continuous system, not disconnected sections.

#### Typography
- Choose a font pairing capable of both large display headlines and dense body copy without losing clarity (e.g. a geometric/humanist sans like Inter or a comparable SF Pro-style alternative).
- Maintain strict visual parity across all typographic contexts — headings, cards, chat text, nav labels, and footer links should share the same type scale and weight logic.

#### Decorative Detail
- Introduce subtle embedded line patterns or hand-drawn-but-refined motifs as background texture — abstract, minimal, and purposeful, never busy or distracting.
- Reserve these accents for reinforcing key sections (hero backdrop, dividers) rather than using them as standalone decoration.

#### Layout & Responsiveness
- Design **mobile-first**: every component is authored for small viewports first, then scaled up — not retrofitted afterward.
- Component architecture must stay visually and structurally consolidated on mobile — no cramped stacking or broken alignment; the same intentionality applied on desktop should carry through to the smallest breakpoint.

#### Content Strategy
- Present product specs and feature details with a clear narrative structure — grouped, scannable sections rather than dense text blocks or raw spec dumps.
- Apply a mindful content hierarchy: lead with value, support with detail, and let visual rhythm (spacing, contrast, motion) guide the eye down the page.

#### Motion, Navigation & Flow
- Scrolling must be smooth and glitch-free — no jank, layout shift, or scroll-jacking that breaks reading rhythm.
- Page navigation and routing should feel instant and predictable — every transition reinforces the user's sense of where they are, never interrupts it.
- The end-to-end user flow — landing → exploring features → conversion — must feel seamless, with no friction points or dead ends.

#### Onboarding
- Onboarding is frictionless by design: minimal required steps, clear progressive disclosure, and no unnecessary gates between a new user and their first meaningful action.

#### Step 1: Set design tokens once
Define in `globals.css` / Tailwind config and reuse everywhere:
- Purple accent + zinc neutrals + black base; a subtle gradient system.
- Semantic colors for priority (high/escalated = warm alert; normal = success).
- One radius (e.g. `rounded-xl`), one shadow scale, one font pairing.
Never hardcode ad-hoc hex per component; use the tokens.

### Step 2: Use shadcn primitives, then customise
Compose `Button`, `Input`, `Card`, `Badge`, `ScrollArea`, `Skeleton`, `Dialog`,
`Tabs`/`Toggle` (for ModeToggle). Then restyle to the purple/black/zinc identity so
it doesn't read as stock shadcn. Primitives give accessibility; your tokens give identity.

### Step 3: Chat surface pattern
- Bubbles: user right (accent-tinted), agent left (surface + subtle border).
- **QuickReplies** chips above the input: *Track order · Product help · Refund · Refund policy · Balance*.
- Streaming: render tokens as they arrive; typing indicator until first token.
- Action chips under a reply when a tool ran ("Order ORD-1002 · Delivered", "Refund prepared", "Escalated").
- **ProductCompareCard**: side-by-side preview with a `[Proceed]` CTA when Products runs.
- Input: Enter-to-send, disabled + spinner while awaiting reply, inline error on failure.

### Step 4: Dual dashboard + escalation queue
- **ModeToggle**: customer view ↔ seller/operations view in the same window.
- Seller view: customer records, stock/catalog, policies, delivery status, logs.
- **Escalation queue**: a `DecisionCard` per pending handoff — verified customer, request, policy check, proposed action, and **Approve / Adjust / Decline (with reason)** buttons. Clicking resolves it and the outcome returns to the conversation.
- Live refresh (poll or subscribe); newest first.
- Empty state: "No escalations — the FTE is handling things."
- Error state: explicit ("Backend unreachable — is it running on :8000?").

### Step 5: Marketing + pricing + demo pages
- **Landing** (SSR): hero + 5–6 sections (problem → how it works → dual dashboard → features → proof → pricing teaser), "Try the demo" / "See features" CTAs, SEO/GEO/AEO metadata.
- **Pricing** (SSR): Core vs Pro tier comparison; yearly-discount nudge inline.
- **Demo playground** (gated, client): guided **StepCard** flow on seed data with the customer↔seller toggle as the centrepiece; ends on pricing + integration request.

### Step 6: States are mandatory
For every data view: **Loading** (`Skeleton`, never blank), **Empty** (a sentence
guiding the next action), **Error** (the actual problem + how to fix).

### Step 7: Keep client/server clean
- Client components (`"use client"`) only where interactivity is needed; SSR marketing pages.
- All backend calls through one `lib/api.js` helper; base URL from `NEXT_PUBLIC_API_URL`.
- UI holds no source-of-truth state; it renders server state and re-fetches.

### Step 8: Polish pass before done
- [ ] Purple/black/zinc committed; consistent radius/spacing/font.
- [ ] Loading/empty/error on every view.
- [ ] Agent actions visible (chips + escalation queue).
- [ ] ModeToggle works and is obvious.
- [ ] Keyboard + focus + contrast checked (esp. on dark surfaces).
- [ ] Doesn't look like default shadcn.

## Example
Add a "thinking" + action state to chat:
1. On send: disable input, show typing indicator bubble.
2. Stream tokens into the agent bubble as they arrive.
3. On tool use: append an action chip ("Refund prepared — pending approval").
4. On escalation: show a chip linking to the seller-view Decision Card.
5. On error: replace indicator with an inline error + retry.

## Troubleshooting
- **Looks generic/templated:** default tokens kept. Commit to purple/black/zinc, one radius, one font; restyle primitives.
- **Layout jumps on load:** no skeletons. Reserve space with `Skeleton` sized to content.
- **Actions invisible to user:** you rendered only text. Add action chips + the escalation queue link.
- **Toggle feels bolted-on:** make ModeToggle a top-level control; persist the mode across views.
- **CORS/failed fetch:** check `NEXT_PUBLIC_API_URL` and backend CORS origins.
- **Poor contrast on dark theme:** verify against tokens; keep focus rings; add aria labels to icon buttons.
