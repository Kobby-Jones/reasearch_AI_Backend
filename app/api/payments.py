from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import PaymentError
from app.models.user import User
from app.schemas.payment import PaymentInitRequest, PaymentInitResponse, PaymentOut
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payment", tags=["payments"])


@router.get("/callback")
def callback(
    reference: str | None = Query(default=None),
    trxref: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Public landing for the Paystack browser redirect.

    Paystack sends the user here (with ``reference`` and ``trxref``) after they
    pay. There is no auth token on this navigation, so we verify by reference,
    finalise the payment, and bounce the browser back to the billing page with
    a status flag. We never surface a raw error page to the user.
    """
    ref = reference or trxref
    base = settings.frontend_url.rstrip("/")
    if not ref:
        return RedirectResponse(url=f"{base}/billing?payment=error", status_code=303)
    try:
        payment = PaymentService(db).verify_by_reference(ref)
        status = "success" if payment.status == "success" else "failed"
    except Exception:
        status = "error"
    return RedirectResponse(
        url=f"{base}/billing?payment={status}&reference={ref}", status_code=303
    )


@router.get("", response_model=list[PaymentOut])
def history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PaymentOut]:
    payments = PaymentService(db).history(user.id, limit=limit, offset=offset)
    return [PaymentOut.model_validate(p) for p in payments]


@router.post("/initiate", response_model=PaymentInitResponse)
def initiate(
    payload: PaymentInitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentInitResponse:
    result = PaymentService(db).initiate(
        user.id,
        payload.plan,
        interval=payload.interval,
        channel=payload.channel,
        momo=payload.momo.model_dump() if payload.momo else None,
    )
    return PaymentInitResponse(**result)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()
    service = PaymentService(db)
    if not service.verify_webhook_signature(body, x_paystack_signature):
        raise PaymentError("Invalid webhook signature.")
    try:
        event = json.loads(body.decode() or "{}")
    except json.JSONDecodeError:
        # Acknowledge so the provider stops retrying a malformed payload.
        return {"status": "ignored", "reason": "invalid_json"}
    return service.handle_webhook(event)


@router.get("/verify/{reference}", response_model=PaymentOut)
def verify(
    reference: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentOut:
    payment = PaymentService(db).verify(reference, user.id)
    return PaymentOut.model_validate(payment)
