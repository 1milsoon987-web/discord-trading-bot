"""Tests for the Discord webhook posting path."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from bot.signals.webhook import post_signals_to_webhook


class _MockResponse:
    def __init__(self, status_code: int = 204) -> None:
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_post_signals_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[dict[str, Any]] = []

    async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any]) -> _MockResponse:
        posted.append({"url": url, "json": json})
        return _MockResponse(204)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await post_signals_to_webhook([], "https://discord.com/api/webhooks/x/y", label="Test")

    assert len(posted) == 1
    payload = posted[0]["json"]
    assert "embeds" in payload
    assert len(payload["embeds"]) == 1
    title = payload["embeds"][0]["title"]
    assert "Test" in title
    # Ensure the payload is JSON-serializable (Discord requires this).
    json.dumps(payload)


@pytest.mark.asyncio
async def test_post_signals_raises_on_empty_url() -> None:
    with pytest.raises(ValueError):
        await post_signals_to_webhook([], "", label=None)
