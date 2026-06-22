"""SurveyCTO connector.

SurveyCTO exposes submissions as wide-format JSON:
  GET https://{server}.surveycto.com/api/v2/forms/data/wide/json/{form_id}

Authenticated with HTTP Basic (the account's email + password, or a dedicated
data-only user). Rows are already mostly flat; we drop the platform's internal
fields and keep the response columns.
"""
from __future__ import annotations

from typing import Callable

from app.connectors.http import ConnectorError

JsonFetch = Callable[..., object]

_META = {"KEY", "SubmissionDate", "starttime", "endtime", "deviceid",
         "subscriberid", "simid", "devicephonenum", "formdef_version", "instanceID"}


def _server(server: str) -> str:
    server = (server or "").strip().rstrip("/")
    if not server:
        raise ConnectorError("A SurveyCTO server name is required.")
    if server.startswith("http"):
        return server
    # accept either "myserver" or "myserver.surveycto.com"
    if not server.endswith(".surveycto.com"):
        server = f"{server}.surveycto.com"
    return f"https://{server}"


def fetch_submissions(
    server: str, username: str, password: str, form_id: str, *, fetch: JsonFetch
) -> list[dict]:
    if not form_id or not form_id.strip():
        raise ConnectorError("A SurveyCTO form ID is required.")
    if not username or not password:
        raise ConnectorError("SurveyCTO username and password are required.")
    url = f"{_server(server)}/api/v2/forms/data/wide/json/{form_id.strip()}"
    data = fetch(url, auth=(username, password))
    rows = data if isinstance(data, list) else (data or {}).get("data", [])
    return [_clean_row(r) for r in rows]


def _clean_row(row: dict) -> dict:
    return {k: v for k, v in (row or {}).items() if k not in _META}
