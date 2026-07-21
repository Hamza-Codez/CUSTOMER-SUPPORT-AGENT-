---
name: user-stories-and-acceptance
description: Turn features for the Digital FTE into clear user stories with testable acceptance criteria and an end-to-end definition of done, so nothing ships half-working. Use when the user asks to write user stories, define acceptance criteria, scope a feature, decide what "done" means, plan sprints/tasks, or verify a feature is complete end to end. Keeps work problem-first, bounded, and demoable, with explicit controls that prove the full flow works.
---

# User Stories & Acceptance

Every feature is a user story with testable acceptance criteria and an end-to-end
definition of done. If it can't be demoed from input to persisted result, it
isn't done. Problem-first, bounded, no half-working merges.

## Principles
1. **Problem-first.** State who needs what and why before any solution.
2. **Testable acceptance.** Each criterion is checkable (given/when/then), not a vibe.
3. **End-to-end done.** Done = the whole path works and is demoable, including failure paths.
4. **Bounded.** Name non-goals so scope can't creep.
5. **No "just".** Don't trivialize engineering effort in stories.

## Story format
```
As a [role], I want [capability], so that [outcome].

Acceptance criteria:
- Given [context], when [action], then [observable result].
- ... (happy path AND at least one failure path)

Non-goals:
- [explicitly out of scope]

Definition of done (end-to-end):
- [ ] Flow works input -> action -> persisted -> visible in UI
- [ ] Failure path handled and shown to user
- [ ] Action is logged/auditable (if state changes)
- [ ] Tested (unit tool + mock-provider integration)
- [ ] Demoable with zero manual setup
```

## Instructions

### Step 1: Write the story problem-first
Lead with role + need + outcome. If you can't name the outcome, the feature isn't ready.

### Step 2: Write acceptance criteria as given/when/then
Cover the happy path and at least one failure path. Each line must be verifiable
by running the system, not by reading code.

### Step 3: Declare non-goals
List what this story does NOT do. This is the primary defense against scope creep.

### Step 4: Attach the end-to-end definition of done
Use the checklist above. A story is not done until every box is true — especially
"demoable with zero manual setup" and "failure path handled".

### Step 5: Map to a success metric
Each story should move a PRD metric (e.g. % auto-resolved, escalation accuracy).
If it maps to no metric, question whether it belongs in this version.

### Step 6: Verify before closing
Run the acceptance criteria live. Watch the UI reflect the result and the audit
log record the action. If any criterion fails, the story stays open.

## Example
```
As a customer, I want to request a refund in chat,
so that I get my money back without waiting for a human.

Acceptance criteria:
- Given order ORD-1002 is refundable, when I ask to refund it,
  then the agent approves it and a ticket is logged.
- Given order ORD-1003 is NOT refundable, when I ask to refund it,
  then the agent refuses and escalates to a human (no refund issued).

Non-goals:
- No real payment execution (stub until a payments API is chosen).
- No partial refunds.

Definition of done:
- [x] Flow works end to end (chat -> tool -> ticket -> dashboard)
- [x] Failure path (non-refundable) refuses + escalates
- [x] Refund action logged as a ticket
- [x] Tested on mock provider (both paths)
- [x] Demoable with zero setup
```

## Troubleshooting
- **Feature "done" but breaks in demo:** DoD skipped the end-to-end check. Re-run acceptance live before closing.
- **Endless scope:** no non-goals declared. Add them; defer anything outside.
- **Untestable criteria ("works well"):** rewrite as given/when/then with an observable result.
- **Failure path forgotten:** require at least one failure criterion per story.
- **Story with no metric:** likely out of scope for this version — confirm before building.
