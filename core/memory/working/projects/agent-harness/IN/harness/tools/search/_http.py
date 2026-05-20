from __future__ import annotations

import json
from typing import Any

import httpx


def raise_for_status_short(resp: httpx.Response, *, provider: str) -> None:
    if resp.is_success:
        return
    body = (resp.text or "")[:500].replace("\r", " ").replace("\n", " ")
    raise ValueError(
        f"{provider} search failed: HTTP {resp.status_code} {resp.reason_phrase}. {body}".strip()
    )


def parse_json(resp: httpx.Response, *, provider: str) -> Any:
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        preview = (resp.text or "")[:300]
        raise ValueError(f"{provider} returned non-JSON response: {preview}") from e
