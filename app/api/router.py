"""Aggregate every feature router under the configured API prefix."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    account,
    analysis,
    audit,
    auth,
    compliance,
    connector,
    dataset,
    notification,
    payments,
    public_report,
    public_survey,
    questionnaire,
    reference,
    reports,
    research,
    status,
    subscription,
    survey,
    viva,
)

api_router = APIRouter()
for module in (
    auth,
    research,
    questionnaire,
    dataset,
    analysis,
    viva,
    reports,
    payments,
    subscription,
    survey,
    public_survey,
    reference,
    connector,
    audit,
    compliance,
    account,
    status,
    notification,
    public_report,
):
    api_router.include_router(module.router)
