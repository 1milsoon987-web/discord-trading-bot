"""Market-data adapters."""

from bot.data.binance import BinanceClient
from bot.data.news import NewsClient
from bot.data.twelvedata import TwelveDataClient

__all__ = ["BinanceClient", "NewsClient", "TwelveDataClient"]
