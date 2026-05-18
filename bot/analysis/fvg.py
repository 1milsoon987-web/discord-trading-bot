"""Fair Value Gap (FVG / imbalance) detection.

A *bullish* FVG forms when a 3-candle sequence leaves a gap between
candle1.high and candle3.low (i.e. candle3.low > candle1.high).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class FVG:
    """A single fair-value gap."""

    index: pd.Timestamp
    direction: str  # "bullish" | "bearish"
    top: float
    bottom: float
    filled: bool = False


def find_fvgs(df: pd.DataFrame, lookback: int = 150) -> list[FVG]:
    """Return unfilled FVGs within the last `lookback` candles."""
    if len(df) < 5:
        return []
    tail = df.tail(lookback).copy()
    highs = tail["high"].values
    lows = tail["low"].values
    idx = tail.index
    gaps: list[FVG] = []
    for i in range(2, len(tail)):
        # bullish FVG: gap up between candles i-2 and i
        if lows[i] > highs[i - 2]:
            top = float(lows[i])
            bottom = float(highs[i - 2])
            filled = bool((lows[i + 1 :] <= bottom).any()) if i + 1 < len(tail) else False
            if not filled:
                gaps.append(FVG(index=idx[i - 1], direction="bullish", top=top, bottom=bottom))
        # bearish FVG: gap down
        elif highs[i] < lows[i - 2]:
            top = float(lows[i - 2])
            bottom = float(highs[i])
            filled = bool((highs[i + 1 :] >= top).any()) if i + 1 < len(tail) else False
            if not filled:
                gaps.append(FVG(index=idx[i - 1], direction="bearish", top=top, bottom=bottom))
    return gaps


def price_in_fvg(price: float, gap: FVG) -> bool:
    """True if `price` is inside the gap."""
    return gap.bottom <= price <= gap.top
