"""Transactional email with a swappable transport.

In development the default ``console`` mode logs the message instead of sending,
so flows work end-to-end with no SMTP credentials. Set ``EMAIL_MODE=smtp`` plus
the SMTP_* settings in production. Sending is always best-effort: a mail failure
never breaks the underlying request (registration, payment, etc.).
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("researchai.email")

# Captured messages in console mode, useful for tests/inspection.
sent_outbox: list[dict] = []


def _brand_wrap(title: str, body_html: str) -> str:
    return (
        "<div style='font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Arial,sans-serif;"
        "background:#f5f7f8;padding:32px 0'>"
        "<div style='max-width:520px;margin:0 auto;background:#fff;border:1px solid #e3e8e7;"
        "border-radius:14px;padding:32px 36px'>"
        "<p style='font-weight:700;font-size:18px;color:#0f766e;margin:0 0 20px'>ResearchAI</p>"
        f"<h1 style='font-size:20px;color:#0f1e1c;margin:0 0 14px'>{title}</h1>"
        f"<div style='font-size:14px;line-height:1.6;color:#374151'>{body_html}</div>"
        "<p style='font-size:12px;color:#8a9794;margin-top:28px'>You are receiving this because you have a "
        "ResearchAI account.</p></div></div>"
    )


def _button(href: str, label: str) -> str:
    return (
        f"<p style='margin:22px 0'><a href='{href}' style='background:#0f766e;color:#fff;"
        "text-decoration:none;padding:11px 20px;border-radius:8px;font-weight:600;"
        f"display:inline-block'>{label}</a></p>"
        f"<p style='font-size:12px;color:#8a9794'>Or paste this link into your browser:<br>{href}</p>"
    )


class EmailService:
    def send(self, to: str, subject: str, html: str, text: str | None = None) -> bool:
        mode = settings.email_mode
        if mode == "disabled":
            return False
        if mode == "console":
            sent_outbox.append({"to": to, "subject": subject, "html": html})
            logger.info("[email:console] to=%s subject=%s", to, subject)
            return True
        # smtp
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.email_from
            msg["To"] = to
            msg.attach(MIMEText(text or "Please view this email in HTML.", "plain"))
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.email_from, [to], msg.as_string())
            return True
        except Exception as exc:  # never propagate into the request
            logger.warning("Email send failed to %s: %s", to, exc)
            return False

    # ---- high-level templates ----
    def send_verification(self, to: str, link: str) -> bool:
        html = _brand_wrap(
            "Confirm your email",
            "<p>Welcome! Please confirm your email address to secure your account.</p>"
            + _button(link, "Confirm email"),
        )
        return self.send(to, "Confirm your ResearchAI email", html)

    def send_password_reset(self, to: str, link: str) -> bool:
        html = _brand_wrap(
            "Reset your password",
            "<p>We received a request to reset your password. This link expires shortly. "
            "If you didn't request this, you can safely ignore this email.</p>"
            + _button(link, "Reset password"),
        )
        return self.send(to, "Reset your ResearchAI password", html)

    def send_receipt(self, to: str, plan: str, amount_minor: int, currency: str, reference: str) -> bool:
        amount = f"{currency} {amount_minor / 100:,.2f}"
        html = _brand_wrap(
            "Payment received",
            f"<p>Thank you. Your <strong>{plan.title()}</strong> subscription is now active.</p>"
            f"<table style='font-size:14px;margin:8px 0'>"
            f"<tr><td style='color:#6b7280;padding:2px 16px 2px 0'>Plan</td><td>{plan.title()}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:2px 16px 2px 0'>Amount</td><td>{amount}</td></tr>"
            f"<tr><td style='color:#6b7280;padding:2px 16px 2px 0'>Reference</td><td>{reference}</td></tr>"
            f"</table>",
        )
        return self.send(to, "Your ResearchAI payment receipt", html)

    def send_quota_warning(self, to: str, metric_label: str, limit: int) -> bool:
        html = _brand_wrap(
            "You've reached a plan limit",
            f"<p>You've used all <strong>{limit}</strong> of your monthly {metric_label} on the free plan. "
            "Upgrade for unlimited use, or your counter resets at the start of next month.</p>"
            + _button(f"{settings.frontend_url.rstrip('/')}/billing", "View plans"),
        )
        return self.send(to, f"You've reached your monthly {metric_label} limit", html)


email_service = EmailService()
