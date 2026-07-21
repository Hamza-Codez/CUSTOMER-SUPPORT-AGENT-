"""A tiny offline chat model that produces REAL tool calls via simple heuristics.

It exists so the scaffold runs end-to-end with no API key and no Ollama install
(great for demos, CI, and tests). Replace with a real provider by setting
MODEL_PROVIDER=openai or ollama. It is intentionally rule-based, not "smart".
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Optional, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

ORDER_RE = re.compile(r"ORD-\d+", re.IGNORECASE)
KB_MARKER_RE = re.compile(r"^\[[^\]]+\]\s*", re.MULTILINE)

SMALL_TALK = {"hi", "hello", "hey", "yo", "thanks", "thank you", "ta", "cheers",
              "bye", "goodbye", "ok", "okay", "got it"}


class MockToolCallingModel(BaseChatModel):
    """Heuristic stand-in for a tool-calling LLM."""

    tools: list = []

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "MockToolCallingModel":
        clone = MockToolCallingModel()
        clone.tools = list(tools)
        return clone

    @property
    def _llm_type(self) -> str:
        return "mock-tool-calling"

    def _last_human_text(self, messages: Sequence[BaseMessage]) -> str:
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                return m.content if isinstance(m.content, str) else str(m.content)
        return ""

    def _tool_results(self, messages: Sequence[BaseMessage]) -> list[str]:
        # Only tool results from the CURRENT turn (after the last human message).
        current: list[str] = []
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                break
            if isinstance(m, ToolMessage):
                current.append(m.content)
        return list(reversed(current))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # If a tool has already run, relay its result as the customer-facing answer.
        # Tool strings are written to be customer-safe, so no rewriting is needed —
        # only the internal [Title] grounding markers are stripped.
        tool_results = self._tool_results(messages)
        if tool_results and isinstance(messages[-1], ToolMessage):
            answer = "\n\n".join(KB_MARKER_RE.sub("", r).strip() for r in tool_results)
            return self._finish(answer)

        text = self._last_human_text(messages)
        lower = text.lower()

        # Small talk needs no tool — and must not trip the KB-miss escalation.
        if lower.strip().strip("!.?,") in SMALL_TALK:
            return self._finish(
                "Hi — I'm the support agent. I can answer product, shipping, "
                "warranty and policy questions, track an order, or help with a refund. "
                "What do you need?"
            )

        order_match = ORDER_RE.search(text)
        order_id = order_match.group(0).upper() if order_match else None

        # --- routing heuristics ---
        if any(w in lower for w in ["angry", "furious", "lawyer", "legal", "sue",
                                    "complaint", "manager", "unacceptable"]):
            return self._call("escalate_to_human",
                              {"summary": text, "order_id": order_id or ""})

        if "refund" in lower and order_id:
            return self._call("process_refund",
                              {"order_id": order_id, "reason": text})

        if order_id:
            return self._call("track_order", {"order_id": order_id})

        if "ticket" in lower:
            return self._call("create_ticket",
                              {"subject": text[:60], "detail": text,
                               "priority": "normal"})

        # Default: answer from the knowledge base.
        return self._call("search_kb", {"query": text})

    def _call(self, name: str, args: dict) -> ChatResult:
        msg = AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}],
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _finish(self, text: str) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
