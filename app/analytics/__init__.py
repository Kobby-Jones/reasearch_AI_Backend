"""Deterministic statistical engine.

CRITICAL DESIGN RULE: every number returned by this package is computed by
pandas / numpy / scipy / statsmodels. No language model is ever consulted here.
The AI layer only *describes* these numbers, it never produces them.
"""
from app.analytics.engine import AnalyticsEngine

__all__ = ["AnalyticsEngine"]
