"""Market-structure analysis: swing highs/lows, BOS, CHoCH.

Definitions:
- Swing high: a candle high greater than the `pivot` highs on either side.
- BOS (Break of Structure): price closes beyond the most recent same-direction swing.
- CHoCH (Change of Character): price closes beyond the opposite swing, signalling a trend flip.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class Swing:
    """A single swing high or low."""

    index: pd.Timestamp
    price: float
    kind: str  # "high" | "low"


@dataclass(slots=True)
class StructureReport:
    """Aggregate market-structure view for a single timeframe."""

    swings: list[Swing]
    last_swing_high: Swing | None
    last_swing_low: Swing | None
    bias: str  # "bullish" | "bearish" | "neutral"
    bos: bool
    choch: bool


def find_swings(df: pd.DataFrame, pivot: int = 3) -> list[Swing]:
    """Find swing highs/lows using a fractal-style pivot of `pivot` bars each side."""
    swings: list[Swing] = []
    highs = df["high"].values
    lows = df["low"].values
    idx = df.index
    for i in range(pivot, len(df) - pivot):
        window_high = highs[i - pivot : i + pivot + 1]
        window_low = lows[i - pivot : i + pivot + 1]
        if highs[i] == window_high.max() and (window_high == highs[i]).sum() == 1:
            swings.append(Swing(idx[i], float(highs[i]), "high"))
        if lows[i] == window_low.min() and (window_low == lows[i]).sum() == 1:
            swings.append(Swing(idx[i], float(lows[i]), "low"))
    return swings


def analyze_structure(df: pd.DataFrame, pivot: int = 3) -> StructureReport:
    """Build a `StructureReport` describing bias, BOS and CHoCH for `df`."""
    swings = find_swings(df, pivot=pivot)
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    last_high = highs[-1] if highs else None
    last_low = lows[-1] if lows else None

    # Determine prior trend from sequence of swings
    bias = "neutral"
    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = highs[-1].price > highs[-2].price
        higher_lows = lows[-1].price > lows[-2].price
        lower_highs = highs[-1].price < highs[-2].price
        lower_lows = lows[-1].price < lows[-2].price
        if higher_highs and higher_lows:
            bias = "bullish"
        elif lower_highs and lower_lows:
            bias = "bearish"

    # Check last close vs last swings
    last_close = float(df["close"].iloc[-1])
    bos = False
    choch = False
    if bias == "bullish" and last_high and last_close > last_high.price:
        bos = True
    elif bias == "bearish" and last_low and last_close < last_low.price:
        bos = True
    if bias == "bullish" and last_low and last_close < last_low.price:
        choch = True
    elif bias == "bearish" and last_high and last_close > last_high.price:
        choch = True

    return StructureReport(
        swings=swings,
        last_swing_high=last_high,
        last_swing_low=last_low,
        bias=bias,
        bos=bos,
        choch=choch,
    )
