"""Aggregate every feature router under the configured API prefix."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    analysis,
    auth,
    dataset,
    payments,
    questionnaire,
    reports,
    research,
    subscription,
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
):
    api_router.include_router(module.router)
