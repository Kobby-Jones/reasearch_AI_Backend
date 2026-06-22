"""KoboToolbox / ODK Central connector.

KoboToolbox exposes a KPI REST API:
  - GET {base}/api/v2/assets/?format=json            -> list of forms (assets)
  - GET {base}/api/v2/assets/{uid}/data/?format=json -> submissions

Auth is a token header: ``Authorization: Token <token>``. ODK Central is
similar enough that the same submission flattening applies to its OData/JSON
rows. Submissions are nested/dotted; we flatten them into flat columns suitable
for tabular analysis and drop Kobo's internal bookkeeping fields.
"""
from __future__ import annotations

from typing import Callable

from app.connectors.http import ConnectorError

# A fetcher: (url, headers) -> parsed JSON
JsonFetch = Callable[..., object]

# Kobo/ODK internal fields that aren't analysis data.
_META_PREFIXES = ("_", "meta/", "formhub/", "__")
_META_EXACT = {
    "start", "end", "today", "deviceid", "subscriberid", "simserial",
    "phonenumber", "username", "__version__",
}


def _base(base_url: str) -> str:
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        raise ConnectorError("A KoboToolbox server URL is required.")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    return base_url


def _headers(token: str) -> dict:
    if not token or not token.strip():
        raise ConnectorError("A KoboToolbox API token is required.")
    return {"Authorization": f"Token {token.strip()}", "Accept": "application/json"}


def list_forms(base_url: str, token: str, *, fetch: JsonFetch) -> list[dict]:
    url = f"{_base(base_url)}/api/v2/assets/"
    data = fetch(url, headers=_headers(token), params={"format": "json"})
    results = (data or {}).get("results", []) if isinstance(data, dict) else (data or [])
    forms = []
    for a in results:
        if a.get("asset_type") and a.get("asset_type") != "survey":
            continue
        forms.append({
            "uid": a.get("uid"),
            "name": a.get("name") or a.get("uid"),
            "submission_count": a.get("deployment__submission_count") or a.get("submission_count") or 0,
        })
    return [f for f in forms if f["uid"]]


def fetch_submissions(base_url: str, token: str, form_uid: str, *, fetch: JsonFetch) -> list[dict]:
    if not form_uid:
        raise ConnectorError("Select a form to import.")
    url = f"{_base(base_url)}/api/v2/assets/{form_uid}/data/"
    data = fetch(url, headers=_headers(token), params={"format": "json"})
    rows = (data or {}).get("results", []) if isinstance(data, dict) else (data or [])
    return [flatten_submission(r) for r in rows]


def _is_meta(key: str) -> bool:
    return key in _META_EXACT or key.startswith(_META_PREFIXES)


def flatten_submission(row: dict, prefix: str = "") -> dict:
    """Flatten one nested submission into flat, analysis-friendly columns.

    Group paths use the last path segment as the column name; repeating groups
    (lists) are summarised as a count, since they can't fit one tabular row.
    """
    flat: dict = {}
    for key, value in (row or {}).items():
        if _is_meta(key):
            continue
        name = key.split("/")[-1]
        col = f"{prefix}{name}" if prefix else name
        if isinstance(value, dict):
            flat.update(flatten_submission(value, prefix=f"{col}_"))
        elif isinstance(value, list):
            flat[f"{col}_count"] = len(value)
        else:
            flat[col] = value
    return flat
