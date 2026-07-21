---
name: auth-and-onboarding
description: Add authentication and first-run onboarding to the Digital FTE using Supabase Auth, protecting the API and giving new users a guided start. Use when the user asks to add login/signup, protect endpoints, add sessions/JWT, gate the dashboard, build an onboarding flow, seed a demo workspace, or handle roles (customer vs human agent). Covers Supabase Auth wiring, protecting FastAPI routes, frontend session handling, and a minimal onboarding path.
---

# Auth & Onboarding

Auth protects actions; onboarding gets a new user to first value fast. Keep both
minimal and end-to-end: a user can sign up, land in a working state, and every
protected action verifies identity.

## Principles
1. **Protect actions, not reads-only-demo.** Anything that changes state or exposes the audit log requires a valid session.
2. **Roles are explicit.** `customer` (chat only) vs `agent` (dashboard + escalations). Enforce server-side.
3. **First value fast.** Onboarding ends with the user seeing the agent work, not a blank app.
4. **Verify on the server.** Never trust the client's claim of who it is; validate the token in FastAPI.

## Instructions

### Step 1: Choose the provider
Use **Supabase Auth** (free tier, matches the DB layer). It issues JWTs the
backend can verify and integrates with the Postgres row-level security if needed.

### Step 2: Frontend sign-up / sign-in
- Use `@supabase/supabase-js` client; email+password or magic link to start.
- Store the session via the Supabase client (it handles refresh); don't hand-roll token storage.
- Send the access token as `Authorization: Bearer <token>` on API calls via the `api.js` helper.

### Step 3: Protect FastAPI routes
```python
from fastapi import Depends, HTTPException, Header

def current_user(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    user = verify_supabase_jwt(token)     # validate signature + expiry
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user=Depends(current_user)):
    ...
```
Protect `/chat`, `/tickets`, and any action endpoint. Leave `/health` open.

### Step 4: Roles and authorization
- Store `role` in user metadata (`customer` | `agent`).
- Gate the dashboard/escalation endpoints to `agent`.
- Return `403` (not `401`) when authenticated but not authorized.

### Step 5: Scope memory to the user
Key conversation memory by `user_id` (or `user_id:session_id`), so sessions are
private per user and can't be read across accounts.

### Step 6: Minimal onboarding flow
1. Sign up -> auto-create a demo workspace (seed a couple of orders + KB docs for this user).
2. Land on the chat with a one-line prompt and 3 suggested messages ("Track ORD-1001", "Refund ORD-1002", "How long is shipping?").
3. First successful agent action -> surface the dashboard link ("See the ticket it just created").
Onboarding is done when the user has seen the agent complete one action.

### Step 7: Verify end-to-end
- Unauthenticated call to `/chat` -> `401`.
- Customer calling an agent-only endpoint -> `403`.
- New signup -> seeded workspace -> can complete one agent action -> sees a ticket.
- Token expiry -> refreshed by client, or clean re-login prompt.

## Example
Gate the tickets dashboard to agents:
1. Add `current_user` dependency to `GET /tickets`.
2. If `user.role != "agent"` -> `403`.
3. Frontend: hide the Tickets nav for customers; show for agents.
4. Test with one customer and one agent account.

## Troubleshooting
- **401 on valid login:** token not sent or wrong header format. Ensure `Authorization: Bearer <token>`.
- **Anyone can read tickets:** route not protected or role not checked. Add the dependency and role gate.
- **Sessions leak across users:** memory keyed only by `session_id`. Key by `user_id` too.
- **Onboarding dead-ends:** no seed data. Seed a demo workspace on signup so the agent has something to act on.
- **Token expired mid-session:** rely on the Supabase client refresh; on failure, prompt a clean re-login.
