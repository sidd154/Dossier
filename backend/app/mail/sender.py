"""SMTP transport, wrapped so the async execution path never blocks."""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.exceptions import UpstreamError
from app.mail.models import SmtpSecurity


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str
    from_name: str | None
    security: SmtpSecurity


def build_message(
    config: SmtpConfig, *, to_email: str, subject: str, body: str
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((config.from_name or "", config.from_email))
    message["To"] = to_email
    message["Subject"] = subject
    domain = config.from_email.split("@")[-1] or None
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(body)
    return message


def _send_sync(config: SmtpConfig, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if config.security == SmtpSecurity.SSL:
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            config.host, config.port, timeout=30, context=context
        )
    else:
        client = smtplib.SMTP(config.host, config.port, timeout=30)

    try:
        client.ehlo()
        if config.security == SmtpSecurity.STARTTLS:
            client.starttls(context=context)
            client.ehlo()
        if config.username:
            client.login(config.username, config.password or "")
        client.send_message(message)
    finally:
        try:
            client.quit()
        except Exception:  # pragma: no cover - best-effort close
            client.close()


async def send_email(
    config: SmtpConfig, message: EmailMessage, *, retries: int = 3
) -> str:
    """Send one message, retrying transient failures. Returns the Message-ID."""
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            await asyncio.to_thread(_send_sync, config, message)
            return str(message["Message-ID"])
        except (smtplib.SMTPException, OSError) as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)

    raise UpstreamError(f"Could not send email: {last_error}")


async def send_test_email(
    config: SmtpConfig, *, to_email: str, organisation_name: str
) -> str:
    message = build_message(
        config,
        to_email=to_email,
        subject=f"{organisation_name} test email",
        body=(
            "This is a test message from the Dossier mail engine.\n\n"
            "If you received it, SMTP is configured correctly."
        ),
    )
    return await send_email(config, message, retries=1)
