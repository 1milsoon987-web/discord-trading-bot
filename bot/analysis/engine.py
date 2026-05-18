"""Confluence scoring engine — combines SMC, indicators and fundamentals into a signal."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from bot.analysis.fundamental import FundamentalSnapshot
from bot.analysis.fvg import FVG, find_fvgs, price_in_fvg
from bot.analysis.indicators import atr, ema_alignment, rsi, rsi_divergence
from bot.analysis.liquidity import LiquidityReport, analyze_liquidity
from bot.analysis.orderblocks import OrderBlock, find_order_blocks, price_in_block
from bot.analysis.structure import StructureReport, analyze_structure


@dataclass(slots=True)
class ConfluenceFactor:
    """A single factor that contributed to the score."""

    name: str
    weight: int  # 0-25 per factor; total weights sum to 100
    triggered: bool
    detail: str


@dataclass(slots=True)
class TradeIdea:
    """Output of the confluence engine for a single asset/timeframe."""

    asset: str
    direction: str  # "long" | "short" | "none"
    confidence: int  # 0-100
    htf_bias: str
    entry_zone_top: float | None
    entry_zone_bottom: float | None
    last_price: float
    atr_value: float
    structure: StructureReport
    matched_block: OrderBlock | None
    matched_fvg: FVG | None
    liquidity: LiquidityReport
    factors: list[ConfluenceFactor] = field(default_factory=list)
    fundamental: FundamentalSnapshot | None = None


# Weights tuned so confluence in same direction reaches a comfortable threshold.
WEIGHTS = {
    "htf_bias": 20,
    "structure_break": 15,
    "order_block": 20,
    "fvg": 10,
    "liquidity_sweep": 15,
    "rsi_divergence": 8,
    "ema_alignment": 7,
    "fundamental_align": 5,
}


def evaluate(
    asset: str,
    df_htf: pd.DataFrame,
    df_ltf: pd.DataFrame,
    fundamental: FundamentalSnapshot | None = None,
) -> TradeIdea:
    """Run full confluence evaluation. `df_htf` = 4h/1d, `df_ltf` = 15m/1h."""
    htf_struct = analyze_structure(df_htf, pivot=3)
    ltf_struct = analyze_structure(df_ltf, pivot=2)
    obs = find_order_blocks(df_ltf, impulse_atr=1.4)
    fvgs = find_fvgs(df_ltf)
    liq = analyze_liquidity(df_ltf)
    last_close = float(df_ltf["close"].iloc[-1])
    atr_val = float(atr(df_ltf, 14).iloc[-1])
    rsi_ltf = rsi(df_ltf["close"], 14)
    div = rsi_divergence(df_ltf["close"], rsi_ltf)
    ema_align = ema_alignment(df_ltf["close"])

    bias = htf_struct.bias
    direction = "long" if bias == "bullish" else "short" if bias == "bearish" else "none"

    # Pick best matching OB / FVG aligned with bias and currently in price proximity
    matched_block: OrderBlock | None = None
    matched_fvg: FVG | None = None
    if direction == "long":
        candidates_ob = [
            ob for ob in obs if ob.direction == "bullish" and price_in_block(last_close, ob, 0.005)
        ]
        if candidates_ob:
            matched_block = max(candidates_ob, key=lambda b: b.index)
        candidates_fvg = [
            g for g in fvgs if g.direction == "bullish" and price_in_fvg(last_close, g)
        ]
        if candidates_fvg:
            matched_fvg = max(candidates_fvg, key=lambda g: g.index)
    elif direction == "short":
        candidates_ob = [
            ob for ob in obs if ob.direction == "bearish" and price_in_block(last_close, ob, 0.005)
        ]
        if candidates_ob:
            matched_block = max(candidates_ob, key=lambda b: b.index)
        candidates_fvg = [
            g for g in fvgs if g.direction == "bearish" and price_in_fvg(last_close, g)
        ]
        if candidates_fvg:
            matched_fvg = max(candidates_fvg, key=lambda g: g.index)

    factors: list[ConfluenceFactor] = []

    # HTF bias
    factors.append(
        ConfluenceFactor(
            "HTF bias",
            WEIGHTS["htf_bias"],
            triggered=direction != "none",
            detail=f"HTF structure bias = {bias}",
        )
    )
    # LTF structure break in same direction
    sb = (
        direction == "long"
        and (ltf_struct.bos or (ltf_struct.choch and ltf_struct.bias == "bullish"))
    ) or (
        direction == "short"
        and (ltf_struct.bos or (ltf_struct.choch and ltf_struct.bias == "bearish"))
    )
    factors.append(
        ConfluenceFactor(
            "LTF structure",
            WEIGHTS["structure_break"],
            triggered=bool(sb),
            detail=f"LTF bias={ltf_struct.bias} BOS={ltf_struct.bos} CHoCH={ltf_struct.choch}",
        )
    )
    # Order block tag
    factors.append(
        ConfluenceFactor(
            "Order block tag",
            WEIGHTS["order_block"],
            triggered=matched_block is not None,
            detail=(
                f"Tagging {matched_block.direction} OB @ {matched_block.bottom:.4f}-{matched_block.top:.4f}"
                if matched_block
                else "No aligned unmitigated OB in price proximity"
            ),
        )
    )
    # FVG
    factors.append(
        ConfluenceFactor(
            "Fair value gap",
            WEIGHTS["fvg"],
            triggered=matched_fvg is not None,
            detail=(
                f"Inside {matched_fvg.direction} FVG @ {matched_fvg.bottom:.4f}-{matched_fvg.top:.4f}"
                if matched_fvg
                else "No active aligned FVG"
            ),
        )
    )
    # Liquidity sweep aligned
    lq_aligned = (direction == "long" and liq.sweep_direction == "sellside") or (
        direction == "short" and liq.sweep_direction == "buyside"
    )
    factors.append(
        ConfluenceFactor(
            "Liquidity sweep",
            WEIGHTS["liquidity_sweep"],
            triggered=lq_aligned,
            detail=f"Sweep direction = {liq.sweep_direction}",
        )
    )
    # RSI divergence
    div_aligned = (direction == "long" and div == "bullish") or (
        direction == "short" and div == "bearish"
    )
    factors.append(
        ConfluenceFactor(
            "RSI divergence",
            WEIGHTS["rsi_divergence"],
            triggered=div_aligned,
            detail=f"divergence={div}",
        )
    )
    # EMA alignment
    ema_aligned = (direction == "long" and ema_align == "bullish") or (
        direction == "short" and ema_align == "bearish"
    )
    factors.append(
        ConfluenceFactor(
            "EMA alignment",
            WEIGHTS["ema_alignment"],
            triggered=ema_aligned,
            detail=f"ema50/200 = {ema_align}",
        )
    )
    # Fundamental alignment
    fund_aligned = False
    if fundamental is not None:
        if direction == "long" and fundamental.sentiment_label == "bullish":
            fund_aligned = True
        elif direction == "short" and fundamental.sentiment_label == "bearish":
            fund_aligned = True
        # F&G extreme contrarian boost for crypto
        if fundamental.sentiment.fear_greed is not None:
            fng = fundamental.sentiment.fear_greed
            if direction == "long" and fng <= 25:
                fund_aligned = True
            elif direction == "short" and fng >= 75:
                fund_aligned = True
    factors.append(
        ConfluenceFactor(
            "Fundamental",
            WEIGHTS["fundamental_align"],
            triggered=fund_aligned,
            detail=(
                f"sentiment={fundamental.sentiment_label} fng={fundamental.sentiment.fear_greed}"
                if fundamental
                else "no fundamental data"
            ),
        )
    )

    score = sum(f.weight for f in factors if f.triggered)

    # Red-news filter: zero the score if high-impact news is imminent
    if fundamental and fundamental.red_news_imminent:
        score = min(score, 30)

    return TradeIdea(
        asset=asset,
        direction=direction if score >= 35 else "none",
        confidence=score,
        htf_bias=bias,
        entry_zone_top=(matched_block.top if matched_block else None),
        entry_zone_bottom=(matched_block.bottom if matched_block else None),
        last_price=last_close,
        atr_value=atr_val,
        structure=htf_struct,
        matched_block=matched_block,
        matched_fvg=matched_fvg,
        liquidity=liq,
        factors=factors,
        fundamental=fundamental,
    )
