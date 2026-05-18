"""Sanity tests for indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bot.analysis.indicators import atr, ema, ema_alignment, rsi


def _make_df(prices: list[float]) -> pd.DataFrame:
    n = len(prices)
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.005 for p in prices],
            "low": [p * 0.995 for p in prices],
            "close": prices,
            "volume": [100.0] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
    )


def test_ema_smoke() -> None:
    s = pd.Series(np.linspace(1, 100, 100))
    out = ema(s, 20)
    assert out.iloc[-1] > out.iloc[0]


def test_atr_smoke() -> None:
    df = _make_df([100.0 + i for i in range(50)])
    a = atr(df, 14)
    assert a.iloc[-1] > 0


def test_rsi_range() -> None:
    s = pd.Series([100.0 + i for i in range(60)])
    r = rsi(s, 14)
    assert r.dropna().between(0, 100).all()


def test_ema_alignment_bullish() -> None:
    df = _make_df([100.0 + i * 0.5 for i in range(250)])
    assert ema_alignment(df["close"]) == "bullish"


def test_ema_alignment_bearish() -> None:
    df = _make_df([200.0 - i * 0.5 for i in range(250)])
    assert ema_alignment(df["close"]) == "bearish"
