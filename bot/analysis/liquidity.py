"""Liquidity zones: equal highs/lows, recent session high/low, sweep detection."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class LiquidityZone:
    """A liquidity pool at a specific price level."""

    price: float
    direction: str  # "buyside" (above price = sells stopped out on long stops) | "sellside"
    label: str  # description: "equal highs", "session low", etc.


@dataclass(slots=True)
class LiquidityReport:
    """Per-timeframe liquidity overview."""

    zones: list[LiquidityZone]
    swept_recently: bool
    sweep_direction: str  # "buyside" | "sellside" | "none"


def find_equal_levels(
    df: pd.DataFrame, tolerance_pct: float = 0.0005, lookback: int = 100
) -> list[LiquidityZone]:
    """Return equal-high and equal-low clusters within `lookback` candles."""
    tail = df.tail(lookback)
    highs = tail["high"].values
    lows = tail["low"].values
    zones: list[LiquidityZone] = []
    used_high: set[int] = set()
    used_low: set[int] = set()
    for i in range(len(tail) - 1):
        for j in range(i + 1, len(tail)):
            if i in used_high or j in used_high:
                continue
            if abs(highs[i] - highs[j]) <= highs[i] * tolerance_pct:
                zones.append(
                    LiquidityZone(
                        price=float((highs[i] + highs[j]) / 2),
                        direction="buyside",
                        label=f"equal highs ({i},{j})",
                    )
                )
                used_high.update({i, j})
                break
    for i in range(len(tail) - 1):
        for j in range(i + 1, len(tail)):
            if i in used_low or j in used_low:
                continue
            if abs(lows[i] - lows[j]) <= lows[i] * tolerance_pct:
                zones.append(
                    LiquidityZone(
                        price=float((lows[i] + lows[j]) / 2),
                        direction="sellside",
                        label=f"equal lows ({i},{j})",
                    )
                )
                used_low.update({i, j})
                break
    return zones


def analyze_liquidity(df: pd.DataFrame, lookback: int = 100) -> LiquidityReport:
    """Detect liquidity zones and recent sweeps."""
    zones = find_equal_levels(df, lookback=lookback)
    if len(df) < 3:
        return LiquidityReport(zones=zones, swept_recently=False, sweep_direction="none")

    tail = df.tail(3)
    last = tail.iloc[-1]
    prev_high = float(df["high"].iloc[-30:-1].max()) if len(df) > 30 else float(df["high"].max())
    prev_low = float(df["low"].iloc[-30:-1].min()) if len(df) > 30 else float(df["low"].min())

    swept_recently = False
    sweep_direction = "none"
    # Buyside sweep: wick takes out prior high then closes below it
    if float(last["high"]) > prev_high and float(last["close"]) < prev_high:
        swept_recently = True
        sweep_direction = "buyside"
    elif float(last["low"]) < prev_low and float(last["close"]) > prev_low:
        swept_recently = True
        sweep_direction = "sellside"

    return LiquidityReport(
        zones=zones, swept_recently=swept_recently, sweep_direction=sweep_direction
    )
