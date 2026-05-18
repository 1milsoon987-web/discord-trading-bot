"""TwelveData adapter for FX and metals (free tier: 8 req/min, 800 req/day)."""

from __future__ import annotations

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import get_settings
from bot.utils.logger import logger

TWELVEDATA_BASE = "https://api.twelvedata.com"


class TwelveDataClient:
    """Async client for the TwelveData /time_series endpoint."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._api_key = get_settings().twelvedata_api_key
        self._client = httpx.AsyncClient(base_url=TWELVEDATA_BASE, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15), reraise=True)
    async def time_series(self, symbol: str, interval: str, outputsize: int = 200) -> pd.DataFrame:
        """Fetch OHLC candles for an FX or metal symbol.

        Args:
            symbol: e.g. "EUR/USD", "XAU/USD"
            interval: TwelveData interval: "15min", "1h", "4h", "1day"
            outputsize: number of candles (max 5000 on paid; 800/day shared budget on free)
        """
        if not self._api_key:
            raise RuntimeError("TWELVEDATA_API_KEY is not set; cannot fetch forex/metal data")
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": self._api_key,
            "format": "JSON",
            "timezone": "UTC",
            "order": "ASC",
        }
        resp = await self._client.get("/time_series", params=params)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") == "error":
            raise RuntimeError(f"TwelveData error for {symbol}: {payload.get('message')}")
        values = payload.get("values")
        if not values:
            raise RuntimeError(f"TwelveData empty payload for {symbol}: {payload}")
        df = pd.DataFrame(values)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        for col in ("open", "high", "low", "close"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        else:
            df["volume"] = 0.0
        df = df.set_index("datetime").sort_index()
        logger.debug(f"TwelveData {symbol} {interval}: {len(df)} rows")
        return df[["open", "high", "low", "close", "volume"]]
