"""Post signals to a Discord webhook (no bot token needed).

Designed for one-shot runs from GitHub Actions cron schedules. Embeds are
built with the same `formatter` helpers used by the persistent bot, then
serialized to webhook JSON and sent via HTTPS POST.
"""

from __future__ import annotations

from typing import Any

import httpx

from bot.signals.formatter import daily_brief_embed, embed_for_signal
from bot.signals.generator import Signal
from bot.utils.logger import logger

WEBHOOK_MAX_EMBEDS_PER_REQUEST = 10
HTTP_TIMEOUT_SECONDS = 30.0


def _embed_to_dict(embed: Any) -> dict[str, Any]:
    """Return a webhook-compatible dict for a `discord.Embed`."""
    return embed.to_dict()


async def post_signals_to_webhook(
    signals: list[Signal],
    webhook_url: str,
    *,
    label: str | None = None,
) -> None:
    """Post a daily brief plus per-signal embeds to a Discord webhook.

    Splits embeds across multiple requests if there are more than the Discord
    per-message limit. If `signals` is empty, posts only the daily brief
    (which gracefully describes the no-setup state).
    """
    if not webhook_url:
        raise ValueError("webhook_url is empty")

    brief = daily_brief_embed(signals)
    if label:
        existing_title = brief.title or "Daily market brief"
        brief.title = f"{existing_title} - {label}"

    embeds: list[dict[str, Any]] = [_embed_to_dict(brief)]
    embeds.extend(_embed_to_dict(embed_for_signal(s)) for s in signals)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        for batch_start in range(0, len(embeds), WEBHOOK_MAX_EMBEDS_PER_REQUEST):
            batch = embeds[batch_start : batch_start + WEBHOOK_MAX_EMBEDS_PER_REQUEST]
            payload = {"embeds": batch}
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code >= 400:
                logger.error(
                    "Webhook post failed: status={} body={}",
                    resp.status_code,
                    resp.text[:300],
                )
                resp.raise_for_status()
            logger.info(
                "Posted {} embed(s) to webhook (batch {}-{})",
                len(batch),
                batch_start,
                batch_start + len(batch),
            )
