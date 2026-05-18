"""Fundamental snapshot used by the confluence engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from bot.data.news import CalendarEvent, NewsClient, SentimentSnapshot


@dataclass(slots=True)
class FundamentalSnapshot:
    """Fundamental view for a single asset."""

    asset: str
    asset_class: str  # "crypto" | "forex" | "metals"
    sentiment: SentimentSnapshot
    upcoming_high_impact: list[CalendarEvent] = field(default_factory=list)

    @property
    def sentiment_label(self) -> str:
        s = self.sentiment.score
        if s > 0.15:
            return "bullish"
        if s < -0.15:
            return "bearish"
        return "neutral"

    @property
    def red_news_imminent(self) -> bool:
        return len(self.upcoming_high_impact) > 0


_CURRENCIES_BY_SYMBOL: dict[str, set[str]] = {
    "EUR/USD": {"EUR", "USD"},
    "GBP/USD": {"GBP", "USD"},
    "USD/JPY": {"USD", "JPY"},
    "XAU/USD": {"USD"},
}


async def collect_fundamental(
    asset: str, asset_class: str, news: NewsClient
) -> FundamentalSnapshot:
    """Build a `FundamentalSnapshot` for `asset`."""
    sentiment = await news.sentiment(asset_class)
    currencies = _CURRENCIES_BY_SYMBOL.get(asset, set())
    upcoming: list[CalendarEvent] = []
    if asset_class in ("forex", "metals"):
        upcoming = await news.high_impact_within(timedelta(hours=2), currencies=currencies)
    return FundamentalSnapshot(
        asset=asset,
        asset_class=asset_class,
        sentiment=sentiment,
        upcoming_high_impact=upcoming,
    )
