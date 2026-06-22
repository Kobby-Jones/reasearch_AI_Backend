"""Google Sheets connector (link-based, no OAuth).

For the common case, a researcher shares a sheet as "anyone with the link can
view" and pastes the link. We extract the spreadsheet id (and optional gid) and
fetch the CSV export, which needs no credentials. Private sheets that require
OAuth are out of scope for this link-based importer and should be shared or
downloaded first; this is surfaced to the user as a clear message.
"""
from __future__ import annotations

import re
from typing import Callable

from app.connectors.http import ConnectorError

TextFetch = Callable[..., str]

_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[#&?]gid=([0-9]+)")


def extract_ids(url: str) -> tuple[str, str | None]:
    if not url or not url.strip():
        raise ConnectorError("A Google Sheets link is required.")
    m = _ID_RE.search(url)
    if not m:
        # allow passing a bare id
        bare = url.strip()
        if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", bare):
            return bare, None
        raise ConnectorError("That doesn't look like a Google Sheets link.")
    gid_m = _GID_RE.search(url)
    return m.group(1), (gid_m.group(1) if gid_m else None)


def csv_export_url(sheet_id: str, gid: str | None) -> str:
    base = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    return f"{base}&gid={gid}" if gid else base


def fetch_csv(url: str, *, fetch: TextFetch) -> str:
    sheet_id, gid = extract_ids(url)
    text = fetch(csv_export_url(sheet_id, gid))
    # A non-public sheet returns Google's HTML sign-in page rather than CSV.
    head = (text or "").lstrip()[:200].lower()
    if head.startswith("<!doctype html") or "<html" in head:
        raise ConnectorError(
            "This sheet isn't publicly viewable. Set sharing to 'Anyone with the link' and try again."
        )
    if not text.strip():
        raise ConnectorError("The sheet appears to be empty.")
    return text
