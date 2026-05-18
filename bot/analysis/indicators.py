"""Classical indicators implemented in pure pandas/numpy."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - close_prev).abs(), (low - close_prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    diff = series.diff()
    gain = diff.clip(lower=0)
    loss = -diff.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def rsi_divergence(close: pd.Series, rsi_series: pd.Series, lookback: int = 30) -> str:
    """Detect simple regular bullish/bearish RSI divergence in last `lookback` bars.

    Returns one of: "bullish", "bearish", "none".
    """
    if len(close) < lookback + 2:
        return "none"
    window_close = close.tail(lookback)
    window_rsi = rsi_series.tail(lookback)
    # Find two most recent lows / highs
    price_lows = window_close.nsmallest(2).sort_index()
    price_highs = window_close.nlargest(2).sort_index()
    if len(price_lows) == 2 and len(price_highs) == 2:
        # bullish: lower low in price, higher low in RSI
        if (
            price_lows.iloc[1] < price_lows.iloc[0]
            and window_rsi.loc[price_lows.index[1]] > window_rsi.loc[price_lows.index[0]]
        ):
            return "bullish"
        # bearish: higher high in price, lower high in RSI
        if (
            price_highs.iloc[1] > price_highs.iloc[0]
            and window_rsi.loc[price_highs.index[1]] < window_rsi.loc[price_highs.index[0]]
        ):
            return "bearish"
    return "none"


def ema_alignment(close: pd.Series) -> str:
    """Return "bullish" if EMA50 > EMA200 and price > EMA50, "bearish" if inverse, else "neutral"."""
    if len(close) < 220:
        return "neutral"
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    price = close.iloc[-1]
    if ema50.iloc[-1] > ema200.iloc[-1] and price > ema50.iloc[-1]:
        return "bullish"
    if ema50.iloc[-1] < ema200.iloc[-1] and price < ema50.iloc[-1]:
        return "bearish"
    return "neutral"
