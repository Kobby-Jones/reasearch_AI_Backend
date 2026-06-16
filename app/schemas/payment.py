from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class MomoInfo(BaseModel):
    network: Literal["mtn", "telecel", "airteltigo"]
    phone: str

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        digits = v.replace(" ", "")
        if not (digits.isdigit() and len(digits) == 10 and digits.startswith("0")):
            raise ValueError("Enter a valid 10-digit mobile money number.")
        return digits


class PaymentInitRequest(BaseModel):
    plan: Literal["basic", "premium"]
    interval: Literal["monthly", "annual"] = "monthly"
    channel: Literal["mobile_money", "card"] = "card"
    momo: MomoInfo | None = None

    @field_validator("momo")
    @classmethod
    def _momo_required(cls, v: MomoInfo | None, info) -> MomoInfo | None:
        if info.data.get("channel") == "mobile_money" and v is None:
            raise ValueError("Mobile money details are required for this channel.")
        return v


class PaymentInitResponse(BaseModel):
    reference: str
    authorization_url: str | None = None
    access_code: str | None = None
    amount: int
    currency: str
    provider: str
    status: str | None = None
    display_text: str | None = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    amount: int
    currency: str
    provider: str
    plan: str
    status: str
    created_at: datetime
    channel: str | None = None
    interval: str | None = None
