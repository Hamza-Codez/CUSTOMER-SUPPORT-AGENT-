---
name: frontend-tailwind-shadcn
description: Build the Next.js frontend for the Digital FTE using Tailwind and shadcn/ui with distinctive, non-generic, AI-native UI/UX. Use when the user asks to build or edit the chat UI, ticket dashboard, or any page/component, to style with Tailwind or shadcn, to improve the look/feel, or to make the interface feel polished and not template-like. Covers component structure, design tokens, chat and agent-status patterns, accessibility, and states (loading, empty, error).
---

# Frontend: Tailwind + shadcn (AI-native, non-generic)

Ship an interface that looks intentional, not scaffolded. Default shadcn is a
starting point, not the finish. Every screen handles loading, empty, and error
states, and makes the agent's actions visible.

## Design principles
1. **Not generic.** Pick one accent, one radius scale, one font pairing, and commit. Avoid the default gray-on-white shadcn look.
2. **AI-native.** Show the agent working: streaming text, tool/action chips ("Refund processed", "Escalated"), and a live audit view. The UI proves it's an agent, not a form.
3. **State-complete.** No screen ships without loading, empty, and error states.
4. **Calm hierarchy.** One primary action per view. Muted secondary text. Generous spacing over dense borders.
5. **Accessible by default.** Keyboard send, focus rings, aria labels, sufficient contrast.

## Instructions

### Step 1: Set design tokens once
Define in `globals.css` / Tailwind config and reuse everywhere:
- One accent (e.g. indigo), semantic colors for priority (high = red, normal = green).
- One radius (e.g. `rounded-xl`), one shadow scale, one font.
Never hardcode ad-hoc hex per component; use the tokens.

### Step 2: Use shadcn primitives, then customise
Install and compose `Button`, `Input`, `Card`, `Badge`, `ScrollArea`, `Skeleton`.
Then restyle: adjust radius, spacing, accent, and typography so it doesn't read
as stock shadcn. The primitives give accessibility; your tokens give identity.

### Step 3: Chat surface pattern
- Message bubbles: user right-aligned (accent-tinted), agent left (surface + subtle border).
- Streaming: render tokens as they arrive; show a typing indicator until first token.
- Action chips: when a tool ran, show a small labeled chip under the reply ("Ticket TCK-0002", "Escalated").
- Input: single-line with Enter-to-send, disabled + spinner while awaiting reply, inline error on failure.

### Step 4: Ticket dashboard pattern
- Card per ticket: id + subject, priority `Badge`, escalation flag, detail, timestamp.
- Live refresh (poll or subscribe); newest first.
- Empty state: friendly prompt ("No tickets yet - process a refund to see one").
- Error state: explicit ("Backend unreachable - is it running on :8000?").

### Step 5: States are mandatory
For every data view implement:
- **Loading:** `Skeleton` placeholders, never a blank screen.
- **Empty:** a sentence guiding the next action.
- **Error:** the actual problem + how to fix.

### Step 6: Keep client/server clean
- Client components (`"use client"`) only where interactivity is needed.
- All backend calls through one `api.js` helper; base URL from `NEXT_PUBLIC_API_URL`.
- UI holds no source-of-truth state; it renders server state and re-fetches.

### Step 7: Polish pass before done
- [ ] One accent, consistent radius/spacing.
- [ ] Loading/empty/error on every view.
- [ ] Agent actions visible (chips/audit).
- [ ] Keyboard + focus + contrast checked.
- [ ] Doesn't look like default shadcn.

## Example
Add a "thinking" state to chat:
1. On send: disable input, show typing indicator bubble.
2. Stream tokens into the agent bubble as they arrive.
3. On tool use: append an action chip ("Refund approved").
4. On error: replace indicator with an inline error + retry.

## Troubleshooting
- **Looks generic/templated:** you kept default tokens. Commit to one accent, radius, and font; restyle primitives.
- **Layout jumps on load:** no skeletons. Reserve space with `Skeleton` sized to content.
- **Actions invisible to user:** you rendered only text. Add action chips + the dashboard link.
- **CORS/failed fetch:** check `NEXT_PUBLIC_API_URL` and backend CORS origins.
- **Poor contrast/inaccessible:** verify against tokens; keep focus rings; add aria labels to icon buttons.
