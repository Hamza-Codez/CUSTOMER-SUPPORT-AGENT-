---
name: user-stories-and-acceptance
description: Turn features for the Digital FTE into clear user stories with testable acceptance criteria and an end-to-end definition of done, so nothing ships half-working. Use when the user asks to write user stories, define acceptance criteria, scope a feature, decide what "done" means, plan sprints/tasks, or verify a feature is complete end to end. Keeps work problem-first, bounded, and demoable, with explicit controls (guardrails, human approval, audit) that prove the full flow works on the Agents SDK + Gemini stack.
---

# User Stories & Acceptance

Every feature is a user story with testable acceptance criteria and an end-to-end
definition of done. If it can't be demoed from input to persisted result, it isn't
done. Problem-first, bounded, no half-working merges.

## Principles
1. **Problem-first.** State who needs what and why before any solution.
2. **Testable acceptance.** Each criterion is checkable (given/when/then), not a vibe.
3. **End-to-end done.** Done = the whole path works and is demoable, including failure and human-approval paths.
4. **Bounded.** Name non-goals so scope can't creep.
5. **Controls are acceptance.** Guardrails, human approval, and audit are testable criteria, not extras.
6. **No "just".** Don't trivialize engineering effort in stories.

## Story format
```
As a [role], I want [capability], so that [outcome].

Acceptance criteria:
- Given [context], when [action], then [observable result].
- ... (happy path AND at least one failure path; add the human-approval path if the action moves money)

Non-goals:
- [explicitly out of scope]

Definition of done (end-to-end):
- [ ] Flow works input -> agent -> tool -> persisted -> visible in UI
- [ ] Failure path handled and shown to user
- [ ] Guardrail / human-approval path enforced where the action is gated
- [ ] Action is logged/auditable (if state changes)
- [ ] Tested (unit tool + mock-provider integration; both paths)
- [ ] Demoable with zero manual setup (boots on MODEL_PROVIDER=mock)
```

## Instructions

### Step 1: Write the story problem-first
Lead with role + need + outcome. Roles include customer, seller, and operator. If you can't name the outcome, the feature isn't ready.

### Step 2: Write acceptance criteria as given/when/then
Cover the happy path and at least one failure path. For money-moving features, add
the human-approval path explicitly. Each line must be verifiable by running the
system, not by reading code.

### Step 3: Declare non-goals
List what this story does NOT do. The primary defense against scope creep.

### Step 4: Attach the end-to-end definition of done
Use the checklist above. Not done until every box is true — especially "demoable
with zero manual setup", "failure path handled", and the guardrail/approval box.

### Step 5: Map to a success metric
Each story should move a platform metric: **deflection rate** (resolved without a
human), **handoff-approval rate** (operators approve as-prepared), **resolution
time**, **CSAT** (from the feedback mailer), or **cost per conversation**. No metric
→ question whether it belongs in this version.

### Step 6: Verify before closing
Run the acceptance criteria live on `mock`. Watch the UI reflect the result and the
audit/escalation log record the action. If any criterion fails, the story stays open.

## Example
```
As a customer, I want to request a refund in chat,
so that I get my money back without waiting for a human.

Acceptance criteria:
- Given order ORD-1002 is within policy and under the auto-cap, when I ask to
  refund it, then the Refunds agent executes it and an audit ticket is logged.
- Given order ORD-1003 is out of policy, when I ask to refund it, then the tool
  guardrail blocks execution and a Decision Card is created (no refund issued).
- Given order ORD-1004 is within policy but OVER the auto-cap, when I ask to
  refund it, then the run pauses for operator approval before any refund.

Non-goals:
- No real payment execution (stub until a payments API is chosen).
- No partial refunds.

Definition of done:
- [x] Flow works end to end (chat -> Refunds agent -> tool -> ticket/Decision Card -> dashboard)
- [x] Failure path (out-of-policy) blocks + escalates via Decision Card
- [x] Over-cap path pauses for human approval before executing
- [x] Refund action logged as an audit ticket
- [x] Tested on mock provider (all three paths)
- [x] Demoable with zero setup
Metric moved: escalation accuracy + deflection rate.
```

## Troubleshooting
- **Feature "done" but breaks in demo:** DoD skipped the end-to-end check. Re-run acceptance live on `mock` before closing.
- **Endless scope:** no non-goals declared. Add them; defer anything outside.
- **Untestable criteria ("works well"):** rewrite as given/when/then with an observable result.
- **Failure path forgotten:** require at least one failure criterion per story; add the human-approval path for gated actions.
- **Story with no metric:** likely out of scope for this version — confirm before building.
