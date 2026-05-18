"""Order Block detection.

A *bullish* order block is the last down candle before a strong up move that breaks
recent structure. A *bearish* OB is the inverse.

This implementation looks for impulse moves (>= `impulse_atr` * ATR) and returns the
preceding opposing candle as the OB zone.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bot.analysis.indicators import atr


@dataclass(slots=True)
class OrderBlock:
    """A single order-block zone."""

    index: pd.Timestamp
    direction: str  # "bullish" | "bearish"
    top: float
    bottom: float
    mitigated: bool = False


def find_order_blocks(
    df: pd.DataFrame, impulse_atr: float = 1.5, lookback: int = 200
) -> list[OrderBlock]:
    """Return unmitigated order blocks within the last `lookback` candles."""
    if len(df) < 30:
        return []
    a = atr(df, 14)
    tail = df.tail(lookback).copy()
    a_tail = a.tail(lookback)
    blocks: list[OrderBlock] = []
    closes = tail["close"].values
    opens = tail["open"].values
    highs = tail["high"].values
    lows = tail["low"].values
    idx = tail.index

    for i in range(1, len(tail) - 1):
        body = abs(closes[i] - opens[i])
        if a_tail.iloc[i] == 0 or pd.isna(a_tail.iloc[i]):
            continue
        if body < impulse_atr * a_tail.iloc[i]:
            continue
        # Bullish OB: strong up candle, previous candle was bearish
        if closes[i] > opens[i] and closes[i - 1] < opens[i - 1]:
            ob = OrderBlock(
                index=idx[i - 1],
                direction="bullish",
                top=float(max(opens[i - 1], closes[i - 1])),
                bottom=float(lows[i - 1]),
            )
            ob.mitigated = bool((lows[i + 1 :] <= ob.bottom).any())
            if not ob.mitigated:
                blocks.append(ob)
        # Bearish OB
        elif closes[i] < opens[i] and closes[i - 1] > opens[i - 1]:
            ob = OrderBlock(
                index=idx[i - 1],
                direction="bearish",
                top=float(highs[i - 1]),
                bottom=float(min(opens[i - 1], closes[i - 1])),
            )
            ob.mitigated = bool((highs[i + 1 :] >= ob.top).any())
            if not ob.mitigated:
                blocks.append(ob)
    return blocks


def price_in_block(price: float, block: OrderBlock, buffer_pct: float = 0.001) -> bool:
    """Return True if `price` is within (or within `buffer_pct`) of the block zone."""
    span = block.top - block.bottom
    buffer = span * buffer_pct
    return (block.bottom - buffer) <= price <= (block.top + buffer)
