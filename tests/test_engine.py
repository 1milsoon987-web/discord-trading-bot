"""End-to-end test of the confluence engine with synthetic data."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bot.analysis.engine import evaluate


def _synthetic_uptrend(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = 100.0
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    opens: list[float] = []
    for _ in range(n):
        opens.append(base)
        step = rng.normal(0.15, 0.4)
        close = base + step
        high = max(open := opens[-1], close) + abs(rng.normal(0.2, 0.1))
        low = min(open, close) - abs(rng.normal(0.2, 0.1))
        highs.append(high)
        lows.append(low)
        closes.append(close)
        base = close
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [100.0] * n},
        index=idx,
    )


def test_engine_returns_idea() -> None:
    df_htf = _synthetic_uptrend(300, seed=1)
    df_ltf = _synthetic_uptrend(300, seed=2)
    idea = evaluate("BTCUSDT", df_htf, df_ltf, fundamental=None)
    assert idea.asset == "BTCUSDT"
    assert 0 <= idea.confidence <= 100
    assert idea.direction in {"long", "short", "none"}
    assert len(idea.factors) == 8
