"""Import an existing Google Form (no OAuth).

A public Google Form's /viewform page embeds its definition in a JSON blob,
``FB_PUBLIC_LOAD_DATA_``. We parse that and map Google's question types to ours.
This works for forms set to "anyone with the link"; private forms that require
sign-in cannot be read this way (surfaced as a clear message). Google can change
this internal shape, so parsing is defensive and skips anything unrecognised.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from app.connectors.http import ConnectorError

TextFetch = Callable[..., str]

# Google item type code -> our question type
_TYPE_MAP = {
    0: "short_text",
    1: "long_text",
    2: "single_choice",   # radio
    3: "dropdown",
    4: "multiple_choice",  # checkboxes
    5: "likert",          # linear scale
    9: "date",
}


def extract_load_data(html: str) -> list:
    m = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*", html or "")
    if not m:
        raise ConnectorError(
            "Couldn't read this Google Form. Make sure it's set to 'Anyone with the link' "
            "and that you pasted the form's view link."
        )
    start = html.index("[", m.end())
    depth, i, n = 0, start, len(html)
    while i < n:
        c = html[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                break
        i += 1
    try:
        return json.loads(html[start:i + 1])
    except ValueError as exc:
        raise ConnectorError("This Google Form could not be parsed.") from exc


def _options(raw_opts) -> list[str]:
    out = []
    for o in raw_opts or []:
        if isinstance(o, list) and o and isinstance(o[0], str) and o[0].strip():
            out.append(o[0].strip())
    return out


def parse_form(html: str) -> dict:
    data = extract_load_data(html)
    try:
        body = data[1]
        raw_items = body[1] or []
    except (IndexError, TypeError) as exc:
        raise ConnectorError("This Google Form has no readable questions.") from exc

    title = None
    if isinstance(body, list) and len(body) > 8 and isinstance(body[8], str):
        title = body[8]
    if not title:
        mt = re.search(r"<title>(.*?)</title>", html or "", re.I | re.S)
        title = (mt.group(1).strip() if mt else "Imported Google Form").replace(" - Google Forms", "")

    items: list[dict] = []
    for it in raw_items:
        try:
            type_code = it[3]
            text = (it[1] or "").strip()
            if type_code not in _TYPE_MAP or not text:
                continue
            qtype = _TYPE_MAP[type_code]
            questions = it[4] or []
            q0 = questions[0] if questions else []
            required = bool(q0[2]) if len(q0) > 2 else False
            item: dict = {"text": text, "type": qtype, "required": required}

            if qtype in ("single_choice", "dropdown", "multiple_choice"):
                opts = _options(q0[1] if len(q0) > 1 else [])
                if len(opts) < 2:
                    continue  # not usable as a choice question
                item["options"] = opts
            elif qtype == "likert":
                pts = _options(q0[1] if len(q0) > 1 else [])
                # linear scale points are numeric labels; keep them as scale labels
                item["scale_labels"] = pts or ["1", "2", "3", "4", "5"]
            items.append(item)
        except (IndexError, TypeError):
            continue

    if not items:
        raise ConnectorError("No supported questions were found in this Google Form.")

    return {
        "title": title,
        "sections": [{"id": "A", "title": "Imported questions", "items": items}],
    }


def import_form(url: str, *, fetch: TextFetch) -> dict:
    if not url or "docs.google.com/forms" not in url:
        raise ConnectorError("Paste a Google Forms link (docs.google.com/forms/...).")
    # normalise to the viewform endpoint
    view = url.split("?")[0].rstrip("/")
    if not view.endswith("viewform"):
        view = view.rsplit("/", 1)[0] + "/viewform" if "/edit" in url else view + "/viewform"
    html = fetch(view)
    return parse_form(html)
