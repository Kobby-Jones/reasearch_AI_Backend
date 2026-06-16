from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    plan: str
    status: str
    start_date: datetime | None = None
    end_date: datetime | None = None


class SubscriptionStatus(BaseModel):
    plan: str
    status: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    interval: str | None = None
    cancel_at_period_end: bool = False
    usage: dict
    limits: dict
