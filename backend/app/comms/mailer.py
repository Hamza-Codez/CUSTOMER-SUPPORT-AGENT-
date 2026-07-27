"""Email delivery — one factory, two implementations.

`mock` is the default and records the message without sending it. That is not
only for convenience: a test suite wired to a real SMTP account is a test suite
that can email a real customer, and the seed data uses plausible-looking
addresses. Sending has to be something you opt into.

SMTP is blocking, so the real provider runs it on a worker thread rather than
stalling the event loop mid-conversation.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


@dataclass
class SendResult:
    status: str  # "sent" | "recorded" | "failed"
    provider: str
    error: str | None = None


class Mailer(Protocol):
    name: str

    async def send(self, to: str, subject: str, html: str, text: str) -> SendResult: ...


class MockMailer:
    """Delivers nothing. The caller still persists the message, so the summary and
    its feedback link can be read back and asserted on."""

    name = "mock"

    async def send(self, to: str, subject: str, html: str, text: str) -> SendResult:
        return SendResult(status="recorded", provider=self.name)


class SmtpMailer:
    name = "smtp"

    def __init__(self, settings) -> None:
        self._s = settings

    def _send_blocking(self, to: str, subject: str, html: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = self._s.email_from
        message["To"] = to
        message["Subject"] = subject
        # Plain text first, HTML second: a client picks the last part it can
        # render, and every client can render the fallback.
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port, timeout=30) as server:
            if self._s.smtp_starttls:
                server.starttls(context=ssl.create_default_context())
            if self._s.smtp_user:
                server.login(self._s.smtp_user, self._s.smtp_password)
            server.send_message(message)

    async def send(self, to: str, subject: str, html: str, text: str) -> SendResult:
        try:
            # smtplib blocks; a slow mail server must not stall the agent run.
            await asyncio.to_thread(self._send_blocking, to, subject, html, text)
            return SendResult(status="sent", provider=self.name)
        except Exception as exc:
            # A failed send is a recorded outcome, not a crashed conversation.
            # The customer already has their answer in chat.
            return SendResult(
                status="failed", provider=self.name, error=f"{type(exc).__name__}: {exc}"
            )


@lru_cache
def get_mailer() -> Mailer:
    settings = get_settings()

    if settings.email_provider == "mock":
        return MockMailer()

    if settings.email_provider == "smtp":
        if not settings.smtp_host:
            raise ValueError(
                "EMAIL_PROVIDER=smtp but SMTP_HOST is empty. "
                "Set it in backend/.env, or use EMAIL_PROVIDER=mock."
            )
        return SmtpMailer(settings)

    raise ValueError(
        f"Unknown EMAIL_PROVIDER {settings.email_provider!r}. Expected 'mock' or 'smtp'."
    )
