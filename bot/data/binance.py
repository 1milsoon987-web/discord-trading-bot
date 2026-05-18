"""Crypto OHLCV adapter with Binance.com -> Binance.US -> KuCoin fallback.

The class is still named `BinanceClient` to keep the public API stable, but it
transparently falls through to alternative providers when the primary host is
geo-blocked or unreachable.
"""

from __future__ import annotations

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.utils.logger import logger

BINANCE_HOSTS = (
    "https://api.binance.com",
    "https://api.binance.us",
)
KUCOIN_BASE = "https://api.kucoin.com"

# Binance interval string -> (kucoin_type, kucoin_minutes)
_KUCOIN_TYPE_MAP: dict[str, tuple[str, int]] = {
    "1m": ("1min", 1),
    "3m": ("3min", 3),
    "5m": ("5min", 5),
    "15m": ("15min", 15),
    "30m": ("30min", 30),
    "1h": ("1hour", 60),
    "2h": ("2hour", 120),
    "4h": ("4hour", 240),
    "6h": ("6hour", 360),
    "8h": ("8hour", 480),
    "12h": ("12hour", 720),
    "1d": ("1day", 1440),
    "1w": ("1week", 10080),
}


def _binance_symbol_to_kucoin(symbol: str) -> str:
    """Convert `BTCUSDT` -> `BTC-USDT` (only USDT/USDC/BTC quotes for now)."""
    for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
        if symbol.endswith(quote):
            return f"{symbol[: -len(quote)]}-{quote}"
    return symbol


class BinanceClient:
    """Async crypto OHLCV client with multi-host fallback."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": "discord-trading-bot/0.1"}
        )
        self._working_binance_host: str | None = None

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), reraise=True)
    async def _try_binance(self, host: str, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        resp = await self._client.get(f"{host}/api/v3/klines", params=params)
        resp.raise_for_status()
        raw = resp.json()
        df = pd.DataFrame(
            raw,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        return df.set_index("open_time")[["open", "high", "low", "close", "volume"]]

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), reraise=True)
    async def _try_kucoin(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        kc_type = _KUCOIN_TYPE_MAP.get(interval)
        if kc_type is None:
            raise RuntimeError(f"KuCoin does not support interval {interval}")
        kc_symbol = _binance_symbol_to_kucoin(symbol)
        params = {"type": kc_type[0], "symbol": kc_symbol}
        resp = await self._client.get(f"{KUCOIN_BASE}/api/v1/market/candles", params=params)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != "200000":
            raise RuntimeError(f"KuCoin error: {payload}")
        raw = payload.get("data", [])
        if not raw:
            raise RuntimeError(f"KuCoin empty payload for {symbol}")
        # KuCoin returns newest-first
        rows = list(reversed(raw[:limit]))
        df = pd.DataFrame(
            rows, columns=["ts", "open", "close", "high", "low", "volume", "turnover"]
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["ts"] = pd.to_datetime(df["ts"].astype(int), unit="s", utc=True)
        return df.set_index("ts")[["open", "high", "low", "close", "volume"]]

    async def klines(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV klines for `symbol`, falling back through providers."""
        # Stick with the host that worked last time
        if self._working_binance_host is not None:
            try:
                df = await self._try_binance(self._working_binance_host, symbol, interval, limit)
                logger.debug(
                    f"{self._working_binance_host} klines {symbol} {interval}: {len(df)} rows"
                )
                return df
            except Exception as e:
                logger.warning(
                    f"Cached Binance host {self._working_binance_host} failed: {e}; rotating"
                )
                self._working_binance_host = None

        for host in BINANCE_HOSTS:
            try:
                df = await self._try_binance(host, symbol, interval, limit)
                self._working_binance_host = host
                logger.info(f"Using Binance host {host}")
                return df
            except Exception as e:
                logger.warning(f"Binance host {host} failed for {symbol}: {e}")

        # Final fallback: KuCoin
        df = await self._try_kucoin(symbol, interval, limit)
        logger.info(f"Using KuCoin for {symbol}: {len(df)} rows")
        return df
