"""Free fundamental-data sources: crypto Fear & Greed, RSS news, ForexFactory calendar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import feedparser  # type: ignore[import-untyped]
import httpx
import pytz
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.utils.logger import logger

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

RSS_FEEDS: dict[str, list[str]] = {
    "crypto": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
    ],
    "forex": [
        "https://www.fxstreet.com/rss/news",
    ],
    "metals": [
        "https://www.kitco.com/rss/KitcoNews.xml",
    ],
}

FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Simple sentiment lexicon — fast, dependency-free
_BULLISH_WORDS = {
    "surge",
    "soar",
    "rally",
    "rallies",
    "bullish",
    "breakout",
    "breakthrough",
    "gain",
    "gains",
    "rise",
    "rises",
    "rising",
    "jump",
    "jumps",
    "spike",
    "spikes",
    "record",
    "high",
    "highs",
    "buy",
    "buying",
    "uptrend",
    "optimistic",
    "positive",
    "boost",
    "growth",
    "expansion",
    "strong",
    "stronger",
    "strengthen",
}
_BEARISH_WORDS = {
    "plunge",
    "crash",
    "tumble",
    "tumbles",
    "bearish",
    "breakdown",
    "fall",
    "falls",
    "drop",
    "drops",
    "decline",
    "declines",
    "sink",
    "sinks",
    "slump",
    "slumps",
    "low",
    "lows",
    "sell",
    "selling",
    "downtrend",
    "pessimistic",
    "negative",
    "loss",
    "losses",
    "weak",
    "weaker",
    "weaken",
    "fear",
    "panic",
    "concern",
}


@dataclass(slots=True)
class CalendarEvent:
    """Economic-calendar event."""

    title: str
    country: str
    impact: str  # "High" | "Medium" | "Low" | "Holiday"
    timestamp_utc: datetime


@dataclass(slots=True)
class SentimentSnapshot:
    """Aggregate sentiment for an asset class."""

    score: float  # -1.0 (very bearish) .. +1.0 (very bullish)
    headlines: list[str]
    fear_greed: int | None = None  # 0-100 crypto F&G index


class NewsClient:
    """Async client for free fundamental data."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "discord-trading-bot/0.1"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def fear_and_greed(self) -> int | None:
        """Return the latest Crypto Fear & Greed index (0..100) or None on failure."""
        try:
            resp = await self._client.get(FEAR_GREED_URL)
            resp.raise_for_status()
            data = resp.json()
            value = int(data["data"][0]["value"])
            logger.debug(f"Fear & Greed: {value}")
            return value
        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")
            return None

    async def _fetch_rss(self, url: str) -> list[str]:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.text)
            return [entry.get("title", "") for entry in parsed.entries[:20]]
        except Exception as e:
            logger.warning(f"RSS fetch failed for {url}: {e}")
            return []

    async def sentiment(self, asset_class: str) -> SentimentSnapshot:
        """Aggregate sentiment for `asset_class` ('crypto'|'forex'|'metals')."""
        feeds = RSS_FEEDS.get(asset_class, [])
        all_titles: list[str] = []
        for url in feeds:
            all_titles.extend(await self._fetch_rss(url))
        score = _score_titles(all_titles) if all_titles else 0.0
        fng: int | None = None
        if asset_class == "crypto":
            fng = await self.fear_and_greed()
        return SentimentSnapshot(score=score, headlines=all_titles[:10], fear_greed=fng)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15), reraise=True)
    async def economic_calendar(self) -> list[CalendarEvent]:
        """Pull this week's ForexFactory calendar (JSON feed)."""
        try:
            resp = await self._client.get(FF_CALENDAR_URL)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            logger.warning(f"ForexFactory calendar fetch failed: {e}")
            return []
        events: list[CalendarEvent] = []
        for item in raw:
            try:
                ts = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=pytz.UTC)
                events.append(
                    CalendarEvent(
                        title=item.get("title", ""),
                        country=item.get("country", ""),
                        impact=item.get("impact", "Low"),
                        timestamp_utc=ts.astimezone(pytz.UTC),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.debug(f"Skipping malformed FF event: {e}")
        logger.debug(f"Economic calendar: {len(events)} events")
        return events

    async def high_impact_within(
        self, window: timedelta, currencies: set[str] | None = None
    ) -> list[CalendarEvent]:
        """Return high-impact events scheduled in the next `window`."""
        events = await self.economic_calendar()
        now = datetime.now(tz=pytz.UTC)
        out: list[CalendarEvent] = []
        for ev in events:
            if ev.impact != "High":
                continue
            if not (now <= ev.timestamp_utc <= now + window):
                continue
            if currencies and ev.country.upper() not in {c.upper() for c in currencies}:
                continue
            out.append(ev)
        return out


def _score_titles(titles: list[str]) -> float:
    """Naive bag-of-words sentiment, returns score in [-1, 1]."""
    bulls = bears = 0
    for t in titles:
        low = t.lower()
        for w in _BULLISH_WORDS:
            if w in low:
                bulls += 1
        for w in _BEARISH_WORDS:
            if w in low:
                bears += 1
    total = bulls + bears
    if total == 0:
        return 0.0
    return (bulls - bears) / total
