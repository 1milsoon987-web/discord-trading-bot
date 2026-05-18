"""Tests for market-structure analysis."""

from __future__ import annotations

import pandas as pd

from bot.analysis.structure import analyze_structure, find_swings


def _make_df(prices: list[float]) -> pd.DataFrame:
    n = len(prices)
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [100.0] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
    )


def test_find_swings_returns_list() -> None:
    prices = [10, 11, 12, 11, 10, 9, 10, 11, 12, 13, 12, 11, 10, 11, 12]
    df = _make_df([float(p) for p in prices])
    swings = find_swings(df, pivot=2)
    assert isinstance(swings, list)


def test_analyze_structure_bullish_trend() -> None:
    # Strict uptrend with small pullbacks
    prices: list[float] = []
    base = 100.0
    for _i in range(30):
        base += 1
        prices.append(base)
        prices.append(base - 0.4)
    df = _make_df(prices)
    rep = analyze_structure(df, pivot=2)
    assert rep.bias in {"bullish", "neutral"}
