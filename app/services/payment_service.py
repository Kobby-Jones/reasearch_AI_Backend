from __future__ import annotations

import hashlib
import hmac
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import PaymentError, ValidationError
from app.models.payment import Payment
from app.repositories.payment_repository import PaymentRepository
from app.repositories.user_repository import UserRepository
from app.services.subscription_service import SubscriptionService


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.payments = PaymentRepository(db)
        self.users = UserRepository(db)
        self.subs = SubscriptionService(db)

    # ---- initialise a transaction ------------------------------------------
    def history(self, user_id: int, limit: int = 100, offset: int = 0) -> list[Payment]:
        return self.payments.list_for_user(user_id, limit=limit, offset=offset)

    def initiate(
        self,
        user_id: int,
        plan: str,
        interval: str = "monthly",
        channel: str = "card",
        momo: dict | None = None,
    ) -> dict:
        if plan not in ("basic", "premium"):
            raise ValidationError("Plan must be 'basic' or 'premium'.")
        if interval not in ("monthly", "annual"):
            raise ValidationError("Interval must be 'monthly' or 'annual'.")
        if channel not in ("mobile_money", "card"):
            raise ValidationError("Channel must be 'mobile_money' or 'card'.")
        if channel == "mobile_money" and not momo:
            raise ValidationError("Mobile money details are required.")
        user = self.users.get(user_id)
        if not user:
            raise ValidationError("User not found.")

        amount = settings.price_for(plan, interval)
        reference = f"RAI-{uuid.uuid4().hex[:16]}"
        provider = settings.payment_provider

        payment = Payment(
            user_id=user_id,
            reference=reference,
            amount=amount,
            currency=settings.default_currency,
            provider=provider,
            plan=plan,
            status="pending",
            channel=channel,
            interval=interval,
        )
        self.payments.add(payment)
        self.db.commit()

        auth_url, access_code, status, display_text = None, None, "pending", None

        if provider == "paystack" and settings.paystack_secret_key:
            if channel == "mobile_money":
                status, display_text = self._paystack_charge_momo(
                    user.email, amount, reference, momo["phone"], momo["network"]
                )
            else:
                auth_url, access_code = self._paystack_init(user.email, amount, reference)
        elif channel == "mobile_money":
            # Dev convenience: no provider key, surface a prompt the client can poll.
            display_text = "Approve the charge on your phone to continue."

        return {
            "reference": reference,
            "authorization_url": auth_url,
            "access_code": access_code,
            "amount": amount,
            "currency": settings.default_currency,
            "provider": provider,
            "status": status,
            "display_text": display_text,
        }

    # Paystack mobile-money provider codes (Ghana). Telecel was Vodafone, which
    # Paystack still identifies as "vod".
    _MOMO_PROVIDER_CODES = {"mtn": "mtn", "telecel": "vod", "airteltigo": "atl"}

    def _paystack_charge_momo(
        self, email: str, amount: int, reference: str, phone: str, network: str
    ) -> tuple[str, str | None]:
        """Trigger an inline mobile-money charge; the user approves on their phone."""
        try:
            resp = httpx.post(
                f"{settings.paystack_base_url}/charge",
                headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
                json={
                    "email": email,
                    "amount": amount,
                    "currency": settings.default_currency,
                    "reference": reference,
                    "mobile_money": {
                        "phone": phone,
                        "provider": self._MOMO_PROVIDER_CODES.get(network, "mtn"),
                    },
                },
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise PaymentError(f"Failed to reach Paystack: {exc}") from exc
        if resp.status_code >= 400:
            raise PaymentError(f"Paystack rejected the charge (HTTP {resp.status_code}).")
        try:
            body = resp.json()
        except ValueError as exc:
            raise PaymentError("Paystack returned an unreadable response.") from exc
        if not body.get("status"):
            raise PaymentError(body.get("message") or "Mobile money charge failed.")
        data = body.get("data") or {}
        # Paystack status here is one of: send_otp, pay_offline, pending, success...
        ps_status = (data.get("status") or "pending").lower()
        status = "success" if ps_status == "success" else "pending"
        display = data.get("display_text") or "Approve the prompt on your phone to complete payment."
        return status, display

    def _paystack_init(self, email: str, amount: int, reference: str) -> tuple[str | None, str | None]:
        try:
            resp = httpx.post(
                f"{settings.paystack_base_url}/transaction/initialize",
                headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
                json={
                    "email": email,
                    "amount": amount,
                    "reference": reference,
                    "currency": settings.default_currency,
                    "callback_url": settings.payment_callback_url,
                },
                timeout=20,
            )
        except httpx.HTTPError as exc:  # network failure shouldn't 500 the API
            raise PaymentError(f"Failed to reach Paystack: {exc}") from exc
        if resp.status_code >= 400:
            raise PaymentError(f"Paystack rejected the request (HTTP {resp.status_code}).")
        try:
            body = resp.json()
        except ValueError as exc:
            raise PaymentError("Paystack returned an unreadable response.") from exc
        if not body.get("status"):
            raise PaymentError(body.get("message") or "Paystack initialization failed.")
        data = body.get("data") or {}
        return data.get("authorization_url"), data.get("access_code")

    # ---- webhook handling ---------------------------------------------------
    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        if not settings.paystack_secret_key:
            # Without a key we cannot verify. Allowed only outside production so
            # local testing works; in production this path must never accept.
            return not settings.is_production
        expected = hmac.new(
            settings.paystack_secret_key.encode(), body, hashlib.sha512
        ).hexdigest()
        return bool(signature) and hmac.compare_digest(expected, signature)

    def handle_webhook(self, event: dict) -> dict:
        data = event.get("data", {})
        reference = data.get("reference")
        if not reference:
            raise ValidationError("Webhook missing reference.")
        payment = self.payments.get_by_reference(reference)
        if payment is None:
            # Not ours (or already pruned). Acknowledge so retries stop.
            return {"status": "ignored", "reason": "unknown_reference"}
        succeeded = event.get("event") == "charge.success"
        # Defence in depth: confirm the amount/currency Paystack reports matches
        # what we asked for, so a tampered or replayed event can't unlock a plan
        # for less than its price.
        if succeeded:
            charged = data.get("amount")
            currency = (data.get("currency") or payment.currency).upper()
            if charged is not None and (
                int(charged) < payment.amount or currency != payment.currency.upper()
            ):
                succeeded = False
        return self._finalise(reference, succeeded=succeeded)

    # ---- manual verify (server-to-server) ----------------------------------
    def verify(self, reference: str, user_id: int) -> Payment:
        payment = self.payments.get_by_reference(reference)
        if not payment or payment.user_id != user_id:
            raise ValidationError("Unknown payment reference.")

        if settings.paystack_secret_key:
            succeeded = self._paystack_verify(reference)
        elif settings.is_production:
            # No key in production: we must not assume success.
            raise PaymentError("Payment verification is not configured.")
        else:
            # Local/dev convenience only.
            succeeded = True

        self._finalise(reference, succeeded)
        refreshed = self.payments.get_by_reference(reference)
        if refreshed is None:  # pragma: no cover - defensive
            raise ValidationError("Unknown payment reference.")
        return refreshed

    # ---- browser callback verify (no auth context) -------------------------
    def verify_by_reference(self, reference: str) -> Payment:
        """Verify a transaction from the Paystack browser redirect.

        The redirect is a top-level navigation with no Authorization header, so
        we can't scope by the logged-in user. The reference is a
        server-generated, unguessable token and we confirm the charge with
        Paystack server-side before activating any plan, so resolving the user
        from the stored payment is safe.
        """
        payment = self.payments.get_by_reference(reference)
        if not payment:
            raise ValidationError("Unknown payment reference.")

        if settings.paystack_secret_key:
            succeeded = self._paystack_verify(reference)
        elif settings.is_production:
            raise PaymentError("Payment verification is not configured.")
        else:
            succeeded = True  # local/dev convenience only

        self._finalise(reference, succeeded)
        refreshed = self.payments.get_by_reference(reference)
        if refreshed is None:  # pragma: no cover - defensive
            raise ValidationError("Unknown payment reference.")
        return refreshed

    def _paystack_verify(self, reference: str) -> bool:
        try:
            resp = httpx.get(
                f"{settings.paystack_base_url}/transaction/verify/{reference}",
                headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise PaymentError(f"Failed to verify with Paystack: {exc}") from exc
        if resp.status_code >= 400:
            return False
        try:
            body = resp.json()
        except ValueError as exc:
            raise PaymentError("Paystack returned an unreadable response.") from exc
        return (body.get("data") or {}).get("status") == "success"

    def _finalise(self, reference: str, succeeded: bool) -> dict:
        payment = self.payments.get_by_reference(reference)
        if not payment:
            raise ValidationError("Unknown payment reference.")
        if payment.status == "success":
            return {"reference": reference, "status": "success", "already_processed": True}

        if succeeded:
            payment.status = "success"
            self.db.flush()
            # auto-activate subscription for the billing interval that was paid
            self.subs.activate(payment.user_id, payment.plan, getattr(payment, "interval", None) or "monthly")
        else:
            payment.status = "failed"
        self.db.commit()
        return {"reference": reference, "status": payment.status, "plan": payment.plan}
