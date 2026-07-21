# Digital FTE — Skill Pack

Seven skills that teach Claude how to build the **Customer Support Agent (Digital FTE)**
consistently, one per architectural concern. Each is a standalone workflow skill
(Category 2) authored per Anthropic's skill guide.

| Skill | Owns |
|---|---|
| `fte-system-architecture` | End-to-end blueprint, contracts, data flow, phasing |
| `fastapi-backend-architecture` | FastAPI layering, endpoints, controls, testing |
| `agent-handoffs-guardrails` | Agent loop, tools, human handoff, policy-in-code |
| `frontend-tailwind-shadcn` | Next.js + Tailwind + shadcn, non-generic AI-native UI |
| `data-flow-and-database` | Store interface, Supabase + pgvector, RAG, swaps |
| `auth-and-onboarding` | Supabase Auth, protected routes, first-run onboarding |
| `user-stories-and-acceptance` | Stories, testable acceptance, end-to-end DoD |

## Design intent
- **Non-overlapping:** one concern each; they compose without collision.
- **Contract-driven:** architecture freezes the seams; every other skill builds behind them.
- **End-to-end:** each skill enforces "input → action → persisted → visible" and named failure paths.
- **Least-error:** policy in code, mock-first testing, auditable actions.

## Install (per skill)
1. Zip the individual skill folder (the one containing `SKILL.md`).
2. Claude.ai → Settings → Capabilities → Skills → Upload.
3. Enable it. Repeat per skill, or deploy the pack org-wide.

## Order of use
1. `fte-system-architecture` (plan the slice)
2. `user-stories-and-acceptance` (define done)
3. Layer skills (`fastapi-backend-architecture`, `agent-handoffs-guardrails`, `data-flow-and-database`, `frontend-tailwind-shadcn`, `auth-and-onboarding`) as the slice needs them.

Each `SKILL.md` follows the guide: kebab-case name, WHAT+WHEN description,
concise actionable steps, an example, and troubleshooting.
