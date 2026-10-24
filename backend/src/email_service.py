"""Shared transactional email transport.

This module deliberately does not log message bodies, recipient addresses, provider responses,
OTP values, API keys, webhook secrets, or other credentials.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def send_transactional_email(
    to_email: str,
    subject: str,
    text_body: str,
    *,
    template_id: str,
    idempotency_key: str | None = None,
) -> None:
    """Send through Resend (preferred) or explicitly configured SMTP.

    Callers should invoke this only after the associated database transaction commits.
    The idempotency key is passed to Resend where supported; durable queuing/outbox tracking
    is a separate responsibility and is not implied by this transport helper.
    """
    if settings.resend_api_key and settings.resend_from_email:
        headers = {
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:256]
        try:
            with httpx.Client(timeout=10.0, follow_redirects=False) as client:
                result = client.post(
                    "https://api.resend.com/emails",
                    headers=headers,
                    json={
                        "from": settings.resend_from_email,
                        "to": [to_email],
                        "subject": subject,
                        "text": text_body,
                        "tags": [{"name": "template", "value": template_id[:50]}],
                    },
                )
            if not 200 <= result.status_code < 300:
                logger.warning("transactional_email_provider_rejected template=%s status=%s",
                               template_id, result.status_code)
                raise RuntimeError(f"Email provider rejected message with HTTP {result.status_code}")
            return
        except httpx.HTTPError as exc:
            logger.warning("transactional_email_transport_error template=%s error_type=%s",
                           template_id, type(exc).__name__)
            raise RuntimeError("Transactional email delivery request failed") from exc

    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("Email delivery is not configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["X-PesaGuard-Template"] = template_id[:100]
    if idempotency_key:
        message["X-PesaGuard-Idempotency-Key"] = idempotency_key[:200]
    message.set_content(text_body)
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10,
                              context=ssl.create_default_context()) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_use_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
