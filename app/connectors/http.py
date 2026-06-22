"""Injectable HTTP access for external data connectors.

Connectors take a fetcher callable so the parsing/flattening logic stays pure
and unit-testable offline. This module provides the real httpx-backed fetchers.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import settings


def _timeout() -> int:
    return getattr(settings, "connector_timeout", 30)


def get_json(url: str, *, headers: dict | None = None, params: dict | None = None,
             auth: tuple[str, str] | None = None) -> Optional[dict | list]:
    try:
        resp = httpx.get(url, headers=headers, params=params, auth=auth, timeout=_timeout())
    except httpx.HTTPError as exc:
        raise ConnectorError(f"Could not reach the service: {exc}") from exc
    if resp.status_code == 401 or resp.status_code == 403:
        raise ConnectorError("Authentication failed. Check your token or credentials.")
    if resp.status_code >= 400:
        raise ConnectorError(f"The service returned an error (HTTP {resp.status_code}).")
    try:
        return resp.json()
    except ValueError as exc:
        raise ConnectorError("The service returned an unreadable response.") from exc


def get_text(url: str, *, headers: dict | None = None, params: dict | None = None) -> str:
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=_timeout(),
                         follow_redirects=True)
    except httpx.HTTPError as exc:
        raise ConnectorError(f"Could not reach the service: {exc}") from exc
    if resp.status_code >= 400:
        raise ConnectorError(f"The service returned an error (HTTP {resp.status_code}).")
    return resp.text


class ConnectorError(Exception):
    """Raised for connector failures; surfaced to the user as a clear message."""
