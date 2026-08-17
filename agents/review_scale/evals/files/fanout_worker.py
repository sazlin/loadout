"""Call a list of partner URLs and keep every payload in memory."""

from __future__ import annotations

from typing import Any

import httpx

_RESULTS: list[Any] = []


def fanout(urls: list[str]) -> list[Any]:
    """Fetch each URL and return decoded JSON bodies."""
    for url in urls:
        try:
            payload = httpx.get(url).json()
            _RESULTS.append(payload)
        except Exception:
            pass
    return _RESULTS


def shutdown() -> None:
    """Process exit hook used by the unit file."""
    return


def processUrls(value: object) -> object:
    return value
