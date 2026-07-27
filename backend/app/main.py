"""FastAPI entrypoint.

Handlers are deliberately thin: validate, delegate to the Runner, shape the
response. No policy logic and no data access lives here — policy belongs to
guardrails and tools, data belongs to `app/tools/`.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from agents import RunContextWrapper, Runner, RunState
from agents.exceptions import (
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    OutputGuardrailTripwireTriggered,
)
from agents.items import HandoffOutputItem, ToolCallOutputItem
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.agents.orchestrator import get_entry_agent
from app.comms.templates import render_thanks_page
from app.comms.widget import render_widget_js
from app.core import audit
from app.core.auth import SiteKeyDep, TenantContext, TenantDep
from app.core.config import get_settings
from app.core.security import (
    TOKEN_TTL,
    dummy_hash,
    hash_password,
    issue_token,
    verify_password,
)
from app.db import get_store, set_store
from app.db.base import (
    FeedbackRecord,
    PolicyRecord,
    IntegrationRequest,
    SiteKeyRecord,
    UsageRecord,
    UserRecord,
)
from app.db.session_store import StoreSession
from app.guardrails.input_guards import REDIRECT_MESSAGE
from app.rag.embeddings import get_embedder
from app.rag.parser import slugify
from app.rag.site_scan import scan_site
from app.handoffs.human_escalation import (
    build_decision_card,
    new_escalation,
    restore_evidence,
    to_public_card,
)
from app.schemas import (
    AccountView,
    ActivityEntry,
    AgentAction,
    Analytics,
    AuthResponse,
    ChatRequest,
    ChatResponse,
    DecisionRequest,
    DecisionResponse,
    EmailPreview,
    EscalationList,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    HealthResponse,
    IntegrationAccepted,
    IntegrationRequestBody,
    IntegrationRequestList,
    IntegrationRequestView,
    LoginRequest,
    OnboardingContext,
    OnboardingResult,
    OrderSummary,
    OverviewResponse,
    PolicySummary,
    ProductSummary,
    ScannedPageView,
    SignupRequest,
    SiteKeyCreate,
    SiteKeyList,
    SiteKeyView,
    SiteScanRequest,
    SiteScanResult,
)

log = logging.getLogger("fte")

UNGROUNDED_REPLY = (
    "I don't want to guess at that, so let me get a colleague to confirm it for "
    "you. Is there anything else I can help with in the meantime?"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_store()
    await store.connect()
    try:
        yield
    finally:
        await store.close()
        set_store(None)


app = FastAPI(
    title="Digital FTE — Agent Platform",
    version="0.3.0",
    lifespan=lifespan,
)

# Open in dev. Tighten `allow_origins` before this is exposed anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_operator(tenant: TenantDep) -> TenantContext:
    """Operator-only routes. A customer token must never reach the queue."""
    if tenant.role != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires an operator token.",
        )
    return tenant



# --- feedback -----------------------------------------------------------------
#
# Deliberately unauthenticated. These are links in an email: the recipient has no
# session and cannot be asked to log in. The token is the capability — unguessable,
# single-conversation, and the record it resolves to names the tenant, so nothing
# is trusted from the URL beyond the token itself.


@app.get("/feedback/{token}", response_class=HTMLResponse)
async def submit_feedback_from_email(token: str, rating: int = 0) -> HTMLResponse:
    """One-click rating straight from a mail client."""
    if rating < 1 or rating > 5:
        return HTMLResponse(render_thanks_page(0, already_recorded=True), status_code=400)

    store = get_store()
    email = await store.get_email_by_token(token)
    if email is None:
        # Same page either way: confirming whether a token exists would let
        # someone probe for valid ones.
        return HTMLResponse(render_thanks_page(rating), status_code=404)

    recorded = await store.record_feedback(
        FeedbackRecord(
            business_id=email.business_id,
            feedback_token=token,
            session_id=email.session_id,
            rating=rating,
        )
    )
    return HTMLResponse(render_thanks_page(rating, already_recorded=not recorded))


@app.post("/feedback/{token}", response_model=FeedbackResponse)
async def submit_feedback(token: str, req: FeedbackRequest) -> FeedbackResponse:
    """Same thing with a comment, for a real form rather than a link."""
    store = get_store()
    email = await store.get_email_by_token(token)
    if email is None:
        raise HTTPException(status_code=404, detail="Unknown or expired feedback link.")

    recorded = await store.record_feedback(
        FeedbackRecord(
            business_id=email.business_id,
            feedback_token=token,
            session_id=email.session_id,
            rating=req.rating,
            comment=req.comment,
        )
    )
    return FeedbackResponse(
        recorded=recorded,
        rating=req.rating,
        message=(
            "Thanks for the feedback."
            if recorded
            else "A rating was already recorded for this conversation."
        ),
    )


@app.get("/dashboard/feedback", response_model=FeedbackSummary)
async def feedback_summary(
    tenant: TenantContext = Depends(require_operator),
) -> FeedbackSummary:
    """CSAT for the operator dashboard."""
    rows = await tenant.store.list_feedback(tenant.business_id, limit=500)
    ratings = {str(n): 0 for n in range(1, 6)}
    for row in rows:
        ratings[str(row.rating)] += 1
    return FeedbackSummary(
        responses=len(rows),
        average_rating=(
            round(sum(r.rating for r in rows) / len(rows), 2) if rows else None
        ),
        ratings=ratings,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness plus which provider and store are actually live.

    Reports a degraded database rather than raising, so this endpoint stays
    usable for exactly the situation it exists to diagnose.
    """
    settings = get_settings()
    db_up = await get_store().health()
    return HealthResponse(
        status="ok" if db_up else "degraded",
        provider=settings.model_provider,
        store=settings.store_kind,
        db="up" if db_up else "down",
    )


# --- action chips -------------------------------------------------------------


def _tool_payload(item: ToolCallOutputItem) -> dict[str, Any] | None:
    """Normalise a tool result to a dict, whatever concrete form it arrived in."""
    output = item.output
    if isinstance(output, dict):
        return output
    dump = getattr(output, "model_dump", None)
    return dump() if callable(dump) else None


def _order_action(payload: dict[str, Any]) -> AgentAction:
    outcome = payload["outcome"]
    if outcome == "identity_mismatch":
        return AgentAction(kind="identity_check_failed", label="Identity not verified")
    if outcome == "not_found":
        return AgentAction(kind="order_not_found", label="Order not found")

    order = payload.get("order") or {}
    ref = order.get("order_id")
    status_text = str(order.get("status", "")).replace("_", " ")
    return AgentAction(
        kind="order_looked_up", label=f"{ref} · {status_text}".strip(" ·"), ref=ref
    )


def _product_action(payload: dict[str, Any]) -> AgentAction:
    products = payload.get("products") or []
    if not products:
        return AgentAction(kind="no_product_match", label="No catalogue match")
    if len(products) == 1:
        p = products[0]
        return AgentAction(kind="product_viewed", label=p["name"], ref=p["product_id"])
    return AgentAction(
        kind="products_compared",
        label=" vs ".join(p["name"] for p in products),
        ref=",".join(p["product_id"] for p in products),
    )


def _policy_action(payload: dict[str, Any]) -> AgentAction:
    passages = payload.get("passages") or []
    if not passages:
        return AgentAction(kind="no_policy_match", label="No grounded policy found")
    return AgentAction(
        kind="policy_cited",
        label=passages[0]["topic"],
        ref=passages[0]["source_ref"],
    )


def _refund_action(payload: dict[str, Any]) -> AgentAction:
    outcome = payload["outcome"]
    if outcome == "executed":
        return AgentAction(
            kind="refund_executed",
            label=f"Refunded {payload.get('amount')}",
            ref=payload.get("refund_id"),
        )
    if outcome == "already_refunded":
        return AgentAction(kind="refund_duplicate", label="Already refunded")
    return AgentAction(kind="refund_refused", label="Refund refused")


def _email_action(payload: dict[str, Any]) -> AgentAction:
    labels = {
        "sent": "Summary emailed",
        "already_sent": "Summary already sent",
        "refused": "Summary not sent — identity unverified",
        "failed": "Summary could not be delivered",
    }
    outcome = payload["outcome"]
    return AgentAction(
        kind=f"email_{outcome}", label=labels.get(outcome, "Summary email")
    )


def collect_actions(result: Any) -> list[AgentAction]:
    """Derive UI action chips from what the agent actually did.

    Every chip is built from a real handoff or a real tool result, so a chip can
    only appear if the thing it describes actually happened.
    """
    actions: list[AgentAction] = []

    for item in result.new_items:
        if isinstance(item, HandoffOutputItem):
            actions.append(
                AgentAction(
                    kind="routed",
                    label=f"Routed to {item.target_agent.name}",
                    ref=item.target_agent.name,
                )
            )
            continue

        if not isinstance(item, ToolCallOutputItem):
            continue
        payload = _tool_payload(item)
        if not payload or "outcome" not in payload:
            continue

        # Which tool produced this is read off the payload's shape rather than
        # tracked separately — the result schemas are disjoint by construction.
        # GreetResult is tested first: it also carries only `outcome`/`message`
        # plus a list, and the EmailResult test below would otherwise claim it.
        if payload.get("outcome") == "greeted":
            actions.append(
                AgentAction(kind="greeted", label="Introduced itself", ref=None)
            )
        elif "products" in payload:
            actions.append(_product_action(payload))
        elif "passages" in payload:
            actions.append(_policy_action(payload))
        elif "refund_id" in payload:
            actions.append(_refund_action(payload))
        elif "escalation_id" in payload:
            actions.append(
                AgentAction(
                    kind="escalated",
                    label="Escalated to a colleague",
                    ref=payload["escalation_id"],
                )
            )
        elif set(payload) <= {"outcome", "message"}:
            # EmailResult: identified by carrying nothing the others carry. The
            # chip never shows the address — the UI has no business displaying it.
            actions.append(_email_action(payload))
        else:
            actions.append(_order_action(payload))

    return actions


# --- chat ---------------------------------------------------------------------


async def load_verified_identity(tenant: TenantContext) -> None:
    """Restore identities proven earlier in this conversation.

    The run context is rebuilt per request, so without this a customer who proved
    who they are in one message is an unverified stranger in the next — and the
    refund guardrail and the mailer, which both read this evidence, would refuse
    everything after the first turn.

    Restoring it is replay of a recorded fact, not of trust: each entry was
    written by `order_lookup` when an email actually matched, under this exact
    `(business_id, session_id)`.
    """
    for record in await tenant.store.get_verifications(
        tenant.business_id, tenant.session_id
    ):
        tenant.verified_orders.add(record.order_id)
        tenant.verified_email = record.email
        tenant.verified_name = record.name


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, tenant: TenantDep) -> ChatResponse:
    return await _run_turn(req, tenant)


@app.post("/chat/public", response_model=ChatResponse)
async def chat_public(req: ChatRequest, tenant: SiteKeyDep) -> ChatResponse:
    """The same turn, entered with a public site key instead of a session token.

    Identical body on purpose — the widget on a seller's storefront must get the
    same agent, the same guardrails and the same audit trail as the hosted
    dashboard, or the thing being demonstrated is not the thing being sold.

    All of the difference is in the dependency: `SiteKeyDep` yields a context
    pinned to `role="customer"` and to the tenant the key belongs to, so nothing
    reachable from here can read the operator queue or another business.
    """
    return await _run_turn(req, tenant)


async def _run_turn(req: ChatRequest, tenant: TenantContext) -> ChatResponse:
    tenant.session_id = req.session_id
    await load_verified_identity(tenant)
    session = StoreSession(
        session_id=req.session_id,
        business_id=tenant.business_id,
        store=tenant.store,
    )

    try:
        result = await Runner.run(
            get_entry_agent(),
            input=req.message,
            context=tenant,
            session=session,
        )
    except InputGuardrailTripwireTriggered as trip:
        info = _guardrail_info(trip)
        await audit.record(
            tenant,
            action="input_guardrail",
            target=req.session_id,
            outcome=str(info.get("verdict", "blocked")),
        )
        return ChatResponse(
            reply=REDIRECT_MESSAGE,
            session_id=req.session_id,
            actions=[AgentAction(kind="blocked", label="Off-topic or unsafe request")],
        )
    except OutputGuardrailTripwireTriggered as trip:
        # The agent produced something it could not support. Say less, not more.
        #
        # Agents that must retrieve before speaking now force a tool call in
        # their own model settings, so reaching here should be rare. It stays as
        # the backstop: an ungrounded claim must never reach a customer.
        info = _guardrail_info(trip)
        log.warning("grounding tripwire: %s", info.get("reason"))
        await audit.record(
            tenant,
            action="grounding_guardrail",
            target=req.session_id,
            outcome="tripped",
            reason=str(info.get("reason")),
        )
        return ChatResponse(
            reply=UNGROUNDED_REPLY,
            session_id=req.session_id,
            actions=[AgentAction(kind="ungrounded_blocked", label="Answer withheld")],
        )
    except MaxTurnsExceeded:
        # The agent got stuck in a loop — most often retrying a tool a guardrail
        # keeps refusing. The customer is owed a human, not a stack trace, and
        # the loop itself is worth having in the audit log.
        log.warning("max turns exceeded in session %s", req.session_id)
        await audit.record(
            tenant,
            action="max_turns_exceeded",
            target=req.session_id,
            outcome="looped",
        )
        return ChatResponse(
            reply=(
                "I'm going round in circles on this one, so let me hand you to a "
                "colleague who can sort it out properly. Sorry about that."
            ),
            session_id=req.session_id,
            actions=[AgentAction(kind="agent_stuck", label="Handed to a colleague")],
        )
    except Exception as exc:
        # The agent run failing is an infrastructure problem (bad key, provider
        # unreachable), not a conversation outcome. Surface it as a clear error
        # rather than a reply that looks like the agent answered.
        log.exception("agent run failed")
        raise HTTPException(
            status_code=502,
            detail=f"Agent run failed: {type(exc).__name__}: {exc}",
        ) from exc

    await _record_usage(tenant, result)
    actions = collect_actions(result)

    # A gated tool paused the run. Nothing has been executed.
    if result.interruptions:
        card, customer_reply = await build_decision_card(
            tenant, list(result.interruptions), req.message
        )
        record = new_escalation(tenant, card, _serialise_state(result))
        await tenant.store.create_escalation(record)
        await audit.record(
            tenant,
            action="approval_required",
            target=record.escalation_id,
            outcome=str(card.get("policy_check", {}).get("reason_code")),
        )
        actions.append(
            AgentAction(
                kind="approval_pending",
                label="Waiting for a colleague to approve",
                ref=record.escalation_id,
            )
        )
        return ChatResponse(
            reply=customer_reply, session_id=req.session_id, actions=actions
        )

    return ChatResponse(
        reply=result.final_output or "",
        session_id=req.session_id,
        actions=actions,
    )


async def _record_usage(tenant: TenantContext, result: Any) -> None:
    """Token accounting for this turn, for cost per conversation (SPEC §16.5).

    Wrapped because a metric is never worth a failed reply: the customer already
    has their answer, and losing one usage row is a rounding error against
    returning them a 500.
    """
    try:
        settings = get_settings()
        usage = result.context_wrapper.usage
        await tenant.store.record_usage(
            UsageRecord(
                business_id=tenant.business_id,
                session_id=tenant.session_id,
                provider=settings.model_provider,
                model=(
                    settings.gemini_model
                    if settings.model_provider == "gemini"
                    else "mock"
                ),
                requests=getattr(usage, "requests", 0) or 0,
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
            )
        )
    except Exception:
        log.exception("could not record usage for session %s", tenant.session_id)


def _guardrail_info(trip: Exception) -> dict[str, Any]:
    result = getattr(trip, "guardrail_result", None)
    info = getattr(getattr(result, "output", None), "output_info", None)
    return info if isinstance(info, dict) else {}


def _plain_context(ctx: Any) -> dict[str, Any]:
    """Serialise only the flat, safe parts of the tenant context.

    Without this the SDK tries to serialise the whole dataclass, which holds a
    live asyncpg pool. Deep-copying that raises, `to_json` fails, and the
    escalation is stored with no run state — so approving records a decision but
    can never execute it. It works on the in-memory store and fails on Postgres,
    which is exactly the kind of difference that only shows up in production.

    Nothing here is trusted on the way back in: resume supplies a live context via
    `context_override` and restores evidence from the Decision Card.
    """
    return {
        "business_id": getattr(ctx, "business_id", None),
        "role": getattr(ctx, "role", None),
        "actor": getattr(ctx, "actor", None),
        "session_id": getattr(ctx, "session_id", None),
    }


def _serialise_state(result: Any) -> dict[str, Any] | None:
    """Serialise a paused run so an operator can resume it later.

    If this fails we still raise the Decision Card: a human being told about a
    paused refund matters far more than resuming it automatically.
    """
    try:
        return result.to_state().to_json(context_serializer=_plain_context)
    except Exception:
        log.exception("could not serialise run state; escalation raised without it")
        return None


# --- operator queue -----------------------------------------------------------


@app.get("/dashboard/escalations", response_model=EscalationList)
async def list_escalations(
    tenant: TenantContext = Depends(require_operator),
    status_filter: str | None = None,
) -> EscalationList:
    records = await tenant.store.list_escalations(
        tenant.business_id, status=status_filter
    )
    return EscalationList(escalations=[to_public_card(r) for r in records])


# --- accounts -----------------------------------------------------------------


async def _account_view(store: Any, user: UserRecord) -> AccountView:
    return AccountView(
        user_id=user.user_id,
        business_id=user.business_id,
        business_name=await store.get_business_name(user.business_id) or "Your store",
        email=user.email,
        name=user.name,
        role=user.role,
    )


def _auth_response(user: UserRecord, account: AccountView) -> AuthResponse:
    return AuthResponse(
        token=issue_token(
            user_id=user.user_id,
            business_id=user.business_id,
            role=user.role,
            email=user.email,
        ),
        expires_in_days=TOKEN_TTL.days,
        account=account,
    )


@app.post("/auth/signup", response_model=AuthResponse, status_code=201)
async def signup(req: SignupRequest) -> AuthResponse:
    """Register a seller and create the store they will own.

    Sign-up creates a *business*, not just a login. Everything here is scoped by
    `business_id`, so an account without one could not read or write a single row.
    """
    store = get_store()
    business_id = f"biz_{uuid.uuid4().hex[:12]}"
    user = UserRecord(
        user_id=f"usr_{uuid.uuid4().hex[:12]}",
        business_id=business_id,
        email=req.email.lower(),
        name=req.name.strip(),
        password_hash=hash_password(req.password),
        role="operator",
    )

    # Business first: a user row pointing at a business that does not exist would
    # violate the foreign key, and the tenant is the thing actually being created.
    await store.create_business(business_id, req.business_name.strip())
    if not await store.create_user(user):
        raise HTTPException(
            status_code=409,
            detail="That email is already registered. Try signing in instead.",
        )

    return _auth_response(user, await _account_view(store, user))


@app.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest) -> AuthResponse:
    store = get_store()
    user = await store.get_user_by_email(req.email)

    # Verify even when there is no such account, against a throwaway hash.
    # Otherwise an unknown email returns in microseconds while a wrong password
    # takes ~240ms, which is a free way to enumerate who has an account.
    ok = verify_password(req.password, user.password_hash if user else dummy_hash())
    if not user or not ok:
        # One message for both cases, for the same reason.
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")

    return _auth_response(user, await _account_view(store, user))


@app.get("/auth/me", response_model=AccountView)
async def me(tenant: TenantDep) -> AccountView:
    """Who the current token belongs to.

    Lets the frontend tell a still-valid session from an expired one without
    inferring it from a 401 on some unrelated call.
    """
    store = get_store()
    if tenant.user_email:
        user = await store.get_user_by_email(tenant.user_email)
        if user:
            return await _account_view(store, user)

    # A demo token has no account behind it, and saying so is more useful than
    # inventing a name for it.
    return AccountView(
        user_id=tenant.actor,
        business_id=tenant.business_id,
        business_name=await store.get_business_name(tenant.business_id)
        or "Demo store",
        email="",
        name="Demo session",
        role=tenant.role,
    )


@app.post("/onboarding/scan", response_model=SiteScanResult)
async def onboarding_scan(
    req: SiteScanRequest,
    tenant: TenantContext = Depends(require_operator),
) -> SiteScanResult:
    """Read the seller's own storefront and propose the policy pages on it.

    Nothing is stored here. This returns candidates and the text we would ingest;
    the seller picks, and `/onboarding/context` does the writing. Splitting the
    two is the whole safeguard — what the agent may quote at a customer should
    never be decided by a heuristic that ran unattended.
    """
    report = await scan_site(req.url)
    await audit.record(
        tenant,
        action="site_scan",
        target=report.site[:120],
        outcome="found" if report.pages else "no_match",
        pages=len(report.pages),
        skipped=len(report.skipped),
    )
    return SiteScanResult(
        site=report.site,
        pages=[
            ScannedPageView(
                url=p.url, title=p.title, topic=p.topic, text=p.text, matched=p.matched
            )
            for p in report.pages
        ],
        skipped=[[url, reason] for url, reason in report.skipped],
        note=report.note,
    )


@app.post("/onboarding/context", response_model=OnboardingResult, status_code=201)
async def onboarding_context(
    req: OnboardingContext,
    tenant: TenantContext = Depends(require_operator),
) -> OnboardingResult:
    """Turn a seller's own policy text into the passages their agent may cite.

    This is what makes a new account useful: until it runs, the agent has nothing
    grounded to say and correctly refuses every policy question. Passages are
    embedded on the way in with whatever provider is configured, so retrieval
    works immediately.
    """
    embedder = get_embedder()
    # Topic and body embedded together: a question often matches the heading
    # more directly than any sentence beneath it.
    vectors = await embedder.embed(
        [draft.topic + "\n" + draft.body for draft in req.policies]
    )

    refs: list[str] = []
    for draft, vector in zip(req.policies, vectors):
        # Authored refs, as with the seeded documents, so a citation stays stable
        # if the seller later reworks the wording.
        ref = f"onboarding.md#{slugify(draft.topic)}"
        refs.append(ref)
        await tenant.store.upsert_policy(
            PolicyRecord(
                business_id=tenant.business_id,
                topic=draft.topic.strip(),
                text=draft.body.strip(),
                source_ref=ref,
                doc="onboarding.md",
            ),
            vector,
        )

    await audit.record(
        tenant,
        action="onboarding_context",
        target=tenant.business_id,
        outcome="stored",
        passages=len(refs),
    )
    return OnboardingResult(
        passages=len(refs),
        source_refs=refs,
        message="Your agent can now answer from these, and only these.",
    )


@app.post("/integrations/request", response_model=IntegrationAccepted, status_code=201)
async def request_integration(
    req: IntegrationRequestBody, tenant: TenantDep
) -> IntegrationAccepted:
    """A seller asking to embed the FTE on their own site (SPEC §16.1).

    Deliberately a record rather than a mailto: the point of the guided path is
    that the request lands somewhere an operator can work through, instead of
    the flow ending in a dead end.
    """
    record = IntegrationRequest(
        request_id=f"int_{uuid.uuid4().hex[:10]}",
        business_id=tenant.business_id,
        contact_name=req.contact_name.strip(),
        contact_email=req.contact_email.strip(),
        website=req.website.strip(),
        platform=req.platform.strip(),
        monthly_conversations=req.monthly_conversations.strip(),
        notes=req.notes.strip(),
    )
    await tenant.store.create_integration_request(record)
    await audit.record(
        tenant,
        action="integration_request",
        target=record.request_id,
        outcome="received",
        platform=record.platform,
    )
    return IntegrationAccepted(
        request_id=record.request_id,
        status="received",
        message=(
            "Thanks — your request is logged and someone will be in touch about "
            "embedding the FTE on your site."
        ),
    )


@app.get("/widget.js")
async def widget_js() -> Response:
    """The embeddable widget.

    Unauthenticated by design: it is a static script that any storefront may
    fetch, and it carries no data. The credential is the `data-fte-key` on the
    seller's own script tag, and it is checked when the widget calls
    `/chat/public`, not here.
    """
    return Response(
        content=render_widget_js(),
        media_type="application/javascript; charset=utf-8",
        # Short, so a fix reaches embedded sites the same day, but long enough
        # that a busy storefront is not refetching it every page view.
        headers={"Cache-Control": "public, max-age=300"},
    )


# --- site keys -----------------------------------------------------------------


def _normalise_origin(raw: str) -> str:
    """A bare domain into a comparable origin.

    Sellers type "mystore.com", browsers send "https://mystore.com". Normalising
    here rather than at comparison time means the stored value is the exact
    string the browser will present, and the check stays a set membership test
    with no clever matching in it.
    """
    value = raw.strip().rstrip("/")
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    if not parsed.netloc:
        return ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _site_key_view(record: SiteKeyRecord) -> SiteKeyView:
    base = get_settings().public_base_url.rstrip("/")
    return SiteKeyView(
        key=record.key,
        label=record.label,
        allowed_origins=list(record.allowed_origins),
        preview=record.preview,
        active=record.active,
        created_at=record.created_at.isoformat(),
        revoked_at=record.revoked_at.isoformat() if record.revoked_at else None,
        snippet=(
            f'<script src="{base}/widget.js" '
            f'data-fte-key="{record.key}" defer></script>'
        ),
    )


@app.post("/site-keys", response_model=SiteKeyView, status_code=201)
async def create_site_key(
    req: SiteKeyCreate,
    tenant: TenantContext = Depends(require_operator),
) -> SiteKeyView:
    """Mint a public key for this tenant's storefront.

    Operator-only: this is the credential that lets a page talk to the agent, so
    issuing one is a seller action, never something the widget can do for itself.
    """
    origins = [o for o in (_normalise_origin(o) for o in req.allowed_origins) if o]

    # Fails closed rather than issuing a key that works everywhere. A preview key
    # is the deliberate exception — it exists to run on a page the seller cannot
    # edit, which is exactly the case where no origin can be declared up front.
    if not origins and not req.preview:
        raise HTTPException(
            status_code=422,
            detail=(
                "A production site key needs at least one allowed origin, e.g. "
                "https://yourstore.com. Pass preview=true for a key that accepts "
                "any origin."
            ),
        )

    record = SiteKeyRecord(
        # `pk_` so a key is recognisable as public on sight, in a log or a paste.
        key=f"pk_{secrets.token_urlsafe(24)}",
        business_id=tenant.business_id,
        label=req.label.strip(),
        allowed_origins=origins,
        preview=req.preview,
    )
    await tenant.store.create_site_key(record)
    await audit.record(
        tenant,
        action="site_key_created",
        target=record.key[:12],
        outcome="preview" if record.preview else "production",
        origins=origins,
    )
    return _site_key_view(record)


@app.get("/site-keys", response_model=SiteKeyList)
async def list_site_keys(
    tenant: TenantContext = Depends(require_operator),
) -> SiteKeyList:
    records = await tenant.store.list_site_keys(tenant.business_id)
    return SiteKeyList(keys=[_site_key_view(r) for r in records])


@app.delete("/site-keys/{key}", status_code=204)
async def revoke_site_key(
    key: str,
    tenant: TenantContext = Depends(require_operator),
) -> Response:
    revoked = await tenant.store.revoke_site_key(tenant.business_id, key)
    if not revoked:
        raise HTTPException(status_code=404, detail="No live key with that id.")
    await audit.record(
        tenant, action="site_key_revoked", target=key[:12], outcome="revoked"
    )
    return Response(status_code=204)


@app.get("/dashboard/integrations", response_model=IntegrationRequestList)
async def list_integrations(
    tenant: TenantContext = Depends(require_operator),
) -> IntegrationRequestList:
    records = await tenant.store.list_integration_requests(tenant.business_id)
    return IntegrationRequestList(
        requests=[
            IntegrationRequestView(
                request_id=r.request_id,
                contact_name=r.contact_name,
                contact_email=r.contact_email,
                website=r.website,
                platform=r.platform,
                monthly_conversations=r.monthly_conversations,
                notes=r.notes,
                status=r.status,
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ]
    )


@app.get("/dashboard/analytics", response_model=Analytics)
async def analytics(
    tenant: TenantContext = Depends(require_operator),
) -> Analytics:
    """The success signals from SPEC §16.5, computed from real records."""
    settings = get_settings()
    usage = await tenant.store.usage_summary(tenant.business_id)
    escalations = await tenant.store.escalation_counts(tenant.business_id)
    feedback = await tenant.store.list_feedback(tenant.business_id, limit=1000)
    audit_entries = await tenant.store.recent_audit(tenant.business_id, limit=1000)

    # Counted from the transcript, not from token usage: accounting arrived later,
    # so a usage-based denominator would report escalations as having happened
    # outside any conversation at all.
    conversations = await tenant.store.conversation_count(tenant.business_id)
    escalated = min(escalations.get("sessions", 0), conversations)
    settled = escalations.get("approved", 0) + escalations.get("declined", 0)
    total_tokens = usage.input_tokens + usage.output_tokens

    # Cost is only meaningful with both a price and real tokens behind it. The
    # mock provider reports zero usage, so a figure derived from it would be a
    # statement about nothing.
    priced = settings.cost_per_mtok_input > 0 or settings.cost_per_mtok_output > 0
    cost_note: str | None = None
    cost_per_conversation: float | None = None

    if not priced:
        cost_note = (
            "Set COST_PER_MTOK_INPUT and COST_PER_MTOK_OUTPUT to price conversations."
        )
    elif total_tokens == 0:
        cost_note = (
            "No token usage recorded yet — the mock provider does not consume any."
            if "mock" in usage.providers or not usage.providers
            else "No token usage recorded yet."
        )
    elif usage.conversations:
        # Divided by the conversations that actually consumed tokens, so the
        # figure is not diluted by history predating the accounting.
        total_cost = (
            usage.input_tokens * settings.cost_per_mtok_input
            + usage.output_tokens * settings.cost_per_mtok_output
        ) / 1_000_000
        cost_per_conversation = round(total_cost / usage.conversations, 6)

    return Analytics(
        conversations=conversations,
        escalated_conversations=escalated,
        deflection_rate=(
            round(1 - (escalated / conversations), 4) if conversations else None
        ),
        escalations={
            k: v for k, v in escalations.items() if k != "sessions"
        },
        handoff_approval_rate=(
            round(escalations.get("approved", 0) / settled, 4) if settled else None
        ),
        csat_responses=len(feedback),
        csat_average=(
            round(sum(f.rating for f in feedback) / len(feedback), 2)
            if feedback
            else None
        ),
        refunds_executed=sum(
            1
            for e in audit_entries
            if e.action == "refund_processor" and e.outcome == "executed"
        ),
        model_requests=usage.model_requests,
        total_tokens=total_tokens,
        tokens_per_conversation=(
            round(total_tokens / usage.conversations, 1)
            if usage.conversations
            else None
        ),
        cost_per_conversation=cost_per_conversation,
        cost_note=cost_note,
    )


@app.get("/dashboard/overview", response_model=OverviewResponse)
async def operations_overview(
    tenant: TenantContext = Depends(require_operator),
) -> OverviewResponse:
    """Records, stock, policies and recent activity — the seller's own lens."""
    orders = await tenant.store.list_orders(tenant.business_id, limit=25)
    products = await tenant.store.list_products(tenant.business_id)
    policies = await tenant.store.list_policies(tenant.business_id)
    activity = await tenant.store.recent_audit(tenant.business_id, limit=20)

    return OverviewResponse(
        orders=[
            OrderSummary(
                order_id=o.order_id,
                customer_name=o.customer_name,
                status=o.status,
                placed_at=o.placed_at,
                eta=o.eta,
                item_count=o.item_count,
                total=o.total,
            )
            for o in orders
        ],
        products=[
            ProductSummary(
                product_id=p.product_id,
                name=p.name,
                price=p.price,
                stock=p.stock,
                in_stock=p.in_stock,
                summary=p.summary,
            )
            for p in products
        ],
        policies=[
            PolicySummary(doc=p.doc, topic=p.topic, source_ref=p.source_ref)
            for p in policies
        ],
        recent_activity=[
            ActivityEntry(
                actor=e.actor,
                action=e.action,
                target=e.target,
                outcome=e.outcome,
                ts=e.ts.isoformat(),
            )
            for e in activity
        ],
        counts={
            "orders": len(orders),
            "products": len(products),
            "policies": len(policies),
            "out_of_stock": sum(1 for p in products if not p.in_stock),
        },
    )


@app.get("/dashboard/emails/{session_id}", response_model=EmailPreview)
async def email_preview(
    session_id: str,
    tenant: TenantContext = Depends(require_operator),
) -> EmailPreview:
    """The summary email sent for a conversation, exactly as it was rendered."""
    record = await tenant.store.get_email_for_session(tenant.business_id, session_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="No summary email was sent for that conversation."
        )
    return EmailPreview(
        subject=record.subject,
        body_html=record.body_html,
        recipient=record.recipient,
        status=record.status,
        feedback_token=record.feedback_token,
    )


@app.post("/escalations/{escalation_id}/decision", response_model=DecisionResponse)
async def decide_escalation(
    escalation_id: str,
    req: DecisionRequest,
    tenant: TenantContext = Depends(require_operator),
) -> DecisionResponse:
    """Approve or decline a Decision Card, resuming the paused run either way."""
    record = await tenant.store.get_escalation(tenant.business_id, escalation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such escalation.")
    if record.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Already {record.status} by {record.resolved_by or 'someone'}.",
        )

    new_status = "approved" if req.decision == "approve" else "declined"

    # Compare-and-set. Two operators clicking Approve at the same moment: one
    # wins, and only one refund can follow.
    claimed = await tenant.store.resolve_escalation(
        tenant.business_id,
        escalation_id,
        status=new_status,
        resolved_by=tenant.actor,
        reason=req.reason,
    )
    if not claimed:
        raise HTTPException(
            status_code=409, detail="This escalation was just resolved by someone else."
        )

    await audit.record(
        tenant,
        action="escalation_decision",
        target=escalation_id,
        outcome=new_status,
        reason=req.reason,
    )

    customer_reply = await _resume(tenant, record, req, new_status)
    return DecisionResponse(
        escalation_id=escalation_id,
        status=new_status,  # type: ignore[arg-type]
        outcome="resumed" if customer_reply is not None else "recorded",
        customer_reply=customer_reply,
    )


async def _resume(
    tenant: TenantContext,
    record: Any,
    req: DecisionRequest,
    new_status: str,
) -> str | None:
    """Continue the paused run with the operator's decision applied.

    The customer's conversation carries on from where it stopped, so the outcome
    arrives in the same thread rather than as a disconnected notification.
    """
    if not record.run_state:
        return None

    tenant.session_id = record.session_id
    # Hand the original run's tool evidence back, or our own guardrails will block
    # the very action the operator just approved. See handoffs/human_escalation.py.
    restore_evidence(tenant, record)
    agent = get_entry_agent()

    try:
        state = await RunState.from_json(
            agent,
            record.run_state,
            # The serialised context carries a dead database pool; this replaces
            # it with the live one from the operator's request.
            context_override=RunContextWrapper(tenant),
        )
        for item in state.get_interruptions():
            if new_status == "approved":
                state.approve(item)
            else:
                state.reject(
                    item,
                    rejection_message=req.reason
                    or "A colleague reviewed this and could not approve it.",
                )

        # Resume on the state alone. Passing `context=` or `session=` here makes
        # the Runner replay the original message and pause all over again, so the
        # refund never executes — the state already carries both.
        result = await Runner.run(agent, state)
    except Exception:
        # The decision is already recorded and is the thing that matters. A failed
        # resume must not make it look like nothing was decided.
        log.exception("could not resume run for %s", record.escalation_id)
        return None

    reply = result.final_output or None
    if reply:
        # Resuming without a session means the outcome is not written to the
        # transcript automatically, so append it: the customer should see the
        # resolution in the same conversation they started.
        try:
            session = StoreSession(
                record.session_id, tenant.business_id, tenant.store
            )
            await session.add_items([{"role": "assistant", "content": reply}])
        except Exception:
            log.exception("could not append resumed reply to session")
    return reply
