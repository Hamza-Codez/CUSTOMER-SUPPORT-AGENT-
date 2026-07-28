# FTE Agent Platform — Product Intent & Vision

*A living intent document. Non-technical by design, with a technical appendix at the end so it stays useful once you start building.*

---

## 1. What We're Building (in one line)

A **Digital Full-Time Employee (FTE)**: an AI agent that e-commerce businesses "hire" to run their frontline operations — customer support, order tracking, product guidance, and policy-compliant refunds — while humans stay in control of every decision that actually matters.

It is **not a chatbot**. A chatbot answers questions. Our FTE *does the job*: it pulls real records through controlled tools, follows the business's own written policies, safely handles routine actions on its own, and prepares the risky or high-value ones as a ready-to-approve decision a human can confirm with a single click.

---

## 2. The Problem, and the Promise

Frontline support is expensive, slow, and inconsistent. Small and mid-sized sellers can't staff support around the clock, and generic chatbots make things worse — they invent answers, can't touch real order data, and can't take a single meaningful action. Customers end up frustrated, and staff burn hours on repetitive lookups.

Our promise is a **reliable, always-on operator** that is grounded in the business's real data and its own policies, that acts within clearly defined limits, and that hands the hard calls to a person — all for the price of a subscription rather than a salary.

---

## 3. Who It's For (the personas)

- **The Business / Seller** — the buyer. Wants lower support cost, faster resolutions, and consistency, without losing control of money-moving decisions.
- **The End Customer** — the person being served. Wants a fast, natural, polite answer and a real resolution, not a runaround.
- **The Human Operator** — the seller's staff member who receives escalations and approves prepared decisions. Wants context handed to them clearly so they can decide in seconds, not minutes.
- **Delivery & Logistics (context source)** — not a user, but a data source the FTE reads from to report accurate order and dispatch status.

---

## 4. Foundational Principles (the non-negotiables)

These are the rules the whole system is built around. Everything else bends to keep these true.

1. **Agent-first architecture.** Built on the OpenAI Agents SDK, using a clean, conventional agent-SDK project structure — not a pile of one-off scripts.
2. **Tools are the data frontier.** The agent never queries the database directly. Every data read or write goes through a defined tool the agent calls. Tools are the only door between the agent and real records.
3. **Grounded, never invented.** Answers about policy, products, and orders come from parsed source documents and live records only. If the FTE doesn't have grounding, it says so and offers a next step — it does not guess.
4. **Cost-efficient by design.** The goal is a well-organized, optimized data operation, not maximum token spend. Specialized agents, scoped retrievals, and caching keep it lean.
5. **Authenticated and audited.** Every user flow is authenticated, and every sensitive record retrieval and action is logged. Who asked, what was accessed, what was done — all traceable.
6. **Human-in-the-loop for consequential actions.** Anything that moves money, changes an order, or falls outside policy is prepared by the agent but confirmed by a human.
7. **Demo-ready on seed data.** A PostgreSQL dummy database backs the initial demos. The system is designed so the same tools that read seed data will later read a real seller's data — the demo is the product, just pointed at sample records.

---

## 5. The Job Description (what the FTE actually does)

Five core responsibilities. Think of these as the roles on the FTE's "employment contract."

### 5.1 Answer customer FAQs, grounded in the business's docs
The FTE answers from a **parsed, structured knowledge base** built from the seller's real policy and help documents — a clean parsing layer so ready-to-use information is always at hand and nothing is invented. Every answer traces back to a source. The chat surfaces **quick clickable suggestions** so the customer doesn't have to type from scratch, e.g.:

> *Track your order · Issue with a purchase · Request a refund · Check balance · Refund policy · Delivery & dispatch*

It also offers quick replies for common policy topics — order processing, dispatch, delivery methods, and so on — pulled from the same grounded source.

### 5.2 Track orders and report status
The FTE looks up an order and reports its real status in plain, friendly language. Before doing anything account-specific, it **verifies identity** — asking for an order ID and/or email first — so it's talking to the right person before it reveals or changes anything. Tone is natural, responsive, and polite throughout.

### 5.3 Explain products and compare options
The FTE explains a product and can put two or more options **side by side as a preview card**, with the relevant differences highlighted and links to explore further. The customer can click straight through to proceed toward a purchase, so a support conversation can gently become a sales moment.

### 5.4 Handle refund requests within policy
The FTE reads the refund request against the seller's actual refund policy and explains the ruling **politely and in a connecting, human way** — not as a cold "denied." When a refund is clearly within policy and under the configured limit, it prepares the action. When it's borderline or out of policy, it escalates.

### 5.5 Escalate to a human when it matters
Complex, emotional, high-value, or out-of-policy cases go to a person — with full context attached. This is a feature, not a failure: the FTE's job is to make the human's decision *fast and easy*, not to make the decision alone.

---

## 6. Two Ways to Deploy

**A) Hosted dual dashboard.** The business logs into our platform, feeds in its context (policies, catalog, FAQs, tone, escalation rules), and runs everything from a single dashboard we host.

**B) Embedded integration.** The FTE drops into the seller's own site and environment, handling support inside their existing experience. Same brain, delivered where their customers already are. When a seller reaches this point in the flow, we present a **clear, guided integration path** (see §16) rather than a raw hand-off.

---

## 7. The Dual Operations Dashboard

One product, two lenses, one window.

- **Customer mode** — the support surface: chat, quick replies, order tracking, product comparison, refund intake.
- **Seller / Operations mode** — the control surface: customer records, stock and catalog, business and store policies, vendor info, delivery service status, escalation queue, and logs.

A single **toggle** flips between customer and seller views in the same window, so a business can *see both sides of the conversation* at once. This dual view is also the heart of the demo and the sales pitch — it's what makes the "digital employee" idea click for a first-time visitor.

---

## 8. How the Agent Thinks (architecture at a glance)

Rather than one do-everything agent, the FTE is a **small team of specialists coordinated by a lead**:

- **Orchestrator (Triage) agent** — reads what the customer wants and routes it to the right specialist.
- **Support/FAQ agent** — grounded answers from parsed docs.
- **Orders agent** — identity verification and order status.
- **Products agent** — explanations and comparisons.
- **Refunds agent** — policy checks and refund preparation.

Why split it up? Specialization means each agent has a tighter job, fewer tools, and clearer rules — which raises accuracy, lowers cost, and makes guardrails easy to enforce. The customer never sees the seams; to them it's one helpful employee.

---

## 9. Handoffs (filling the gap)

There are two kinds of handoff, and they're different on purpose.

### 9.1 Agent-to-agent (internal routing)
The orchestrator hands a conversation to a specialist, carrying the context along so the customer never repeats themselves. This is invisible plumbing — it just makes the FTE feel coherent.

### 9.2 Agent-to-human (escalation) — the important one
The FTE prepares the decision; the human confirms it. A handoff to a person is triggered when:

- The action **moves money or changes an order** (refunds, cancellations, address changes above a threshold).
- The request is **out of policy** or genuinely ambiguous.
- The customer is **upset, at risk of churning, or explicitly asks for a human**.
- Confidence in a grounded answer is **too low**.

**The "Decision Card" pattern.** When escalating, the FTE doesn't just dump the chat on a human. It hands over a compact, ready-to-act card:

> *Customer:* Ayesha K. (verified via order + email)
> *Request:* Refund for Order #10432 — item arrived damaged
> *Policy check:* Within 30-day damaged-goods window → **eligible**
> *Proposed action:* Refund $59.00 to original method
> *One click:* **✅ Approve refund** · **✏️ Adjust** · **❌ Decline (with reason)**

The human reads it in seconds and confirms. This is exactly the "ready to click OK" experience from the original vision — the FTE does 95% of the work, the human owns the final call.

**Continuity.** Whatever the human decides flows back into the same conversation, so the customer gets a seamless response and the whole exchange stays logged.

---

## 10. Guardrails (filling the gap)

Three layers, checked in order.

### 10.1 Entry guardrails (before the agent acts)
- **Authentication & identity** — verify order ID / email before revealing or changing account data.
- **Scope check** — keep the conversation on-topic (support, orders, products, refunds); politely redirect off-topic or unsafe requests.
- **Abuse / injection filter** — screen for hostile input and attempts to manipulate the agent into ignoring its rules.

### 10.2 Grounding guardrails (while the agent reasons)
- **Retrieval-only answers** — respond from parsed docs and live records, not from the model's imagination.
- **Confidence threshold** — if grounding is weak, say so and route to a person rather than guessing.
- **No policy improvisation** — the FTE quotes and applies the seller's policy; it does not invent exceptions.

### 10.3 Action guardrails (before anything is committed)
- **Refund and spend caps** — auto-actions only under configured limits; everything above goes to human approval.
- **Irreversible-action approval** — cancellations, refunds, and data changes require confirmation.
- **Rate & repetition limits** — protect against loops and abuse.
- **Audit logging** — every action, who/what/when, written to the record.

---

## 11. Tools & the Data Frontier (filling the gap)

**The core rule:** the agent has no direct database access. It only sees what tools return, and only changes what tools allow. Tools are the frontier — the controlled, observable, cost-managed border between a language model and real business data.

### 11.1 The tool catalog (starting set)
- **Order lookup** — fetch order + status by ID/email (read).
- **Product catalog** — fetch product details and comparison data (read).
- **Policy retriever** — pull the relevant grounded policy/FAQ passage (read, RAG).
- **Refund processor** — prepare/execute a refund within limits (write, gated).
- **Email / mailer** — send themed summary + feedback emails via SMTP (write).
- **Human escalation** — open a Decision Card for an operator (write, handoff).

### 11.2 Tool-calling optimization (the cost-efficiency engine)
This is where "not a generic chatbot" becomes real.

- **Least privilege** — each agent only gets the tools its job needs; the Support agent can't issue refunds.
- **Scoped, structured returns** — tools return only the fields needed, in a typed shape, so the model spends fewer tokens reasoning over data.
- **Caching** — frequently requested, slow-changing data (policies, catalog) is cached rather than re-fetched every turn.
- **Minimal calls** — the orchestrator batches and sequences lookups instead of firing redundant queries.
- **Idempotent writes** — refund/email actions are safe against accidental repeats.
- **Full observability** — every tool call is logged for cost tracking, debugging, and audit.

---

## 12. Context Feed (what the agent needs to know)

Before an FTE can work for a business, that business "trains its new hire" by supplying context. Onboarding intake collects:

- **Policies** — refund, returns, shipping, order processing, dispatch, delivery.
- **Product catalog** — items, attributes, pricing, comparison points.
- **FAQ / help docs** — parsed into the structured knowledge base.
- **Brand voice** — tone, do's and don'ts, greeting style.
- **Escalation rules & thresholds** — refund caps, what always needs a human, who receives escalations.
- **Store, vendor, and delivery details** — so status reporting is accurate.

This intake is also a natural place to ask the seller the "important details as context feed" the FTE will rely on — the more precise the feed, the sharper the employee.

---

## 13. User Stories & Flows (filling the gap)

### Representative user stories
- *As a customer,* I want to check my order status without waiting for a human, so that I get a fast, clear answer any time of day.
- *As a customer,* I want a refund on a damaged item, so that I'm made whole without a fight.
- *As a seller,* I want risky decisions prepared for me and safe ones handled automatically, so that I save time without losing control.
- *As an operator,* I want escalations delivered with full context, so that I can approve or decline in seconds.
- *As a seller evaluating the product,* I want to experience both sides in a demo, so that I can see the value before I pay.

### Flow 1 — Order tracking (happy path)
Customer opens chat → taps **"Track your order"** → FTE asks for order ID/email → verifies identity → Orders agent calls *order lookup* tool → reports real status in friendly language → offers next steps ("Anything else — returns, refund, product help?").

### Flow 2 — Refund within policy
Customer taps **"Request a refund"** → FTE verifies identity → Refunds agent calls *policy retriever* + *order lookup* → confirms it's within policy and under the cap → explains the ruling warmly → prepares refund → (if under auto-limit) executes and confirms; (if above) opens a **Decision Card** for the operator.

### Flow 3 — Refund out of policy → escalation (the Amazon scenario)
A business on the **basic monthly plan** gets full customer support in real time. A customer requests a refund that's outside the window. The FTE checks policy, sees it doesn't qualify automatically, and rather than bluntly refusing, it **escalates with a Decision Card**: customer details, the reason, the policy that applies, and a proposed action — so the human can click **✅ Approve** or **❌ Decline (with reason)** in one step. Policy-compliant, human-owned, effortless.

### Flow 4 — Product comparison
Customer asks "which of these two is better for X?" → Products agent calls *product catalog* → returns a **side-by-side preview card** highlighting the differences → offers "See more options" and a **click-to-proceed** path toward purchase.

### Flow 5 — Seller onboarding / integration
Seller signs up → provides context feed (§12) → tries the FTE on their own sample data → when they want it live, the flow presents a **guided integration path** with a clear method to request embedding into their site (not a dead end — a real next step, see §16).

### Flow 6 — Demo experience
Visitor signs up → enters the **demo playground** → is walked step-by-step through info cards and clickables → toggles between **customer and seller** views → ends on pricing + a guided integration request. (Detailed in §16.)

---

## 14. Follow-Up & Communications

After a resolved conversation, the FTE sends a **themed email** via SMTP containing a **summary of what happened and a short feedback form**. This does three jobs at once: it closes the loop for the customer, it collects satisfaction data, and it acts as **passive advertising** for the platform (a subtle, well-designed "handled by your FTE" footprint). The mailer follows a consistent branded theme rather than a plain text dump.

---

## 15. Pricing & Tiers

A simple, two-tier subscription model:

- **Monthly** — **$20/month**. Full frontline customer support: FAQs, order tracking, product help, in-policy refund preparation, and human handoff for the rest.
- **Yearly** — the same, billed annually at a **discount** for committing up front.

The two tiers are pitched as **service levels** (e.g., a core plan vs. a higher plan with more integrations, higher automation limits, or deeper analytics — to be finalized). The Amazon-style scenario sits on the basic monthly plan and still gets the full real-time support-plus-handoff experience.

---

## 16. Go-To-Market: The Website & Demo

The demo *is* the go-to-market motion, so both the site and the demo get serious design attention.

### 16.1 A multi-page site (not one endless landing page)
Distinct, navigable pages the visitor reaches on click:

- **Home / Landing** — the pitch.
- **Features** — the FTE's capabilities, framed as its "job description."
- **Pricing** — the two tiers, clearly compared.
- **Login / Sign up** — the gateway to the demo.
- **Demo playground** — the interactive experience (post sign-up).
- **Integrations / Request access** — the guided path for sellers ready to embed.

### 16.2 The landing page
A professional, conversion-oriented sequence: a strong **hero section** plus **5–6 sections** (e.g., problem → how it works → dual dashboard → features → proof/social → pricing teaser), each with clear **"Try the demo"** and **"See features"** calls to action. Written to double as the sales pitch and as SEO/GEO/AEO-optimized content so it's discoverable by both search engines and AI answer engines.

### 16.3 Look & feel
**Purple, black, and zinc** in a refined gradient palette — minimalist, modern, and premium. The aesthetic should say "something new and worth trying," not "another support tool."

### 16.4 The demo playground (the crown jewel)
After sign-up, the visitor enters a guided playground designed to feel like **discovering something new and genuinely fun to use**:

- **Step-by-step**, with **info cards and clickables** at each stage so nobody gets lost.
- A **customer ↔ seller toggle** in the same window, so the visitor experiences *both* sides of the FTE.
- Runs on the **PostgreSQL seed database**, so every lookup, comparison, and refund feels real.
- Ends on **pricing and a clear, guided integration request** — turning "that was cool" into "how do I get this on my store?"

The whole flow should let a first-timer *see the possibilities and the ease*, and leave wanting it.

### 16.5 Success signals (what "good" looks like)
Worth defining early so the demo and product can be judged: **support deflection rate** (handled without a human), **handoff quality** (how often operators approve as-prepared), **resolution time**, **customer satisfaction (CSAT)** from the feedback form, and **cost per conversation**.

---

## 17. Out of Scope for v1 (to keep focus)

Explicitly *not* in the first version, so effort stays sharp: multi-language support, voice, deep third-party marketplace integrations beyond the guided request flow, and fully automated (human-free) money movement above the auto-limit. These are roadmap, not launch.

---

## Appendix A — Suggested Project Structure (for the build phase)

A clean split: **Next.js** frontend, **FastAPI** backend running the **OpenAI Agents SDK**, **PostgreSQL** for data, **uv** for Python packaging.

```
fte-platform/
├── frontend/                     # Next.js (App Router)
│   ├── app/
│   │   ├── page.tsx              # landing
│   │   ├── features/
│   │   ├── pricing/
│   │   ├── login/
│   │   ├── signup/
│   │   ├── demo/                 # demo playground (customer/seller toggle)
│   │   └── dashboard/            # dual operations dashboard
│   ├── components/
│   └── lib/
│
└── backend/                      # FastAPI + OpenAI Agents SDK
    ├── pyproject.toml            # managed by uv
    ├── .env                      # GEMINI_API_KEY, DB creds, SMTP — never committed
    ├── app/
    │   ├── main.py               # FastAPI entrypoint (served by uvicorn)
    │   ├── api/                  # HTTP routes
    │   │   ├── chat.py
    │   │   ├── auth.py
    │   │   └── webhooks.py
    │   ├── agents/               # agent definitions
    │   │   ├── orchestrator.py   # triage / routing
    │   │   ├── support_agent.py
    │   │   ├── orders_agent.py
    │   │   ├── products_agent.py
    │   │   └── refunds_agent.py
    │   ├── tools/                # THE DATA FRONTIER — all DB access lives here
    │   │   ├── orders.py
    │   │   ├── products.py
    │   │   ├── policies.py       # RAG retrieval
    │   │   ├── refunds.py
    │   │   └── email.py          # SMTP themed mailer
    │   ├── guardrails/
    │   │   ├── input_guards.py
    │   │   ├── grounding_guards.py
    │   │   └── action_guards.py
    │   ├── handoffs/
    │   │   └── human_escalation.py   # Decision Card logic
    │   ├── rag/
    │   │   ├── parser.py         # parse docs → structured knowledge base
    │   │   └── retriever.py
    │   ├── db/
    │   │   ├── models.py
    │   │   ├── session.py
    │   │   └── seed.py           # PostgreSQL dummy data for demos
    │   ├── core/
    │   │   ├── config.py         # env loading
    │   │   ├── auth.py           # authenticated flows
    │   │   └── logging.py        # audit / retrieval logs
    │   └── schemas/              # typed request/response shapes
    └── tests/
```

---

## Appendix B — Tech Stack & Integration Notes

- **Frontend:** Next.js
- **Backend:** FastAPI, run with **uvicorn**, dependencies managed by **uv** (fast Rust-based package manager)
- **Database:** PostgreSQL (dummy/seed data for demos, same tools point to real data later)
- **Agent framework:** OpenAI Agents SDK
- **Model / API:** Gemini API key, stored in `.env`
- **Email:** SMTP for the themed summary + feedback mailer

**One integration note worth checking early:** the OpenAI Agents SDK is model-flexible and can drive non-OpenAI models like Gemini, typically through an OpenAI-compatible client/endpoint or a LiteLLM adapter. Confirm the exact, current integration path when you start building — SDK details evolve, and you'll want to validate that the Agents SDK's tool-calling and handoff features behave as expected against Gemini before committing the architecture to it.

---

*This document captures the intent and the vision. It intentionally leaves implementation detail loose so it stays useful as a north star while the stack (Next.js · PostgreSQL · FastAPI/uv · OpenAI Agents SDK · Gemini) gets built underneath it.*