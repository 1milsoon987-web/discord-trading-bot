"""SL/TP placement and risk:reward calculation."""

from __future__ import annotations

from dataclasses import dataclass

from bot.analysis.engine import TradeIdea


@dataclass(slots=True)
class TradePlan:
    """Concrete entry / SL / TP plan derived from a `TradeIdea`."""

    entry: float
    stop_loss: float
    take_profits: list[float]
    rr_to_tp1: float


def build_plan(idea: TradeIdea, atr_multiplier: float = 1.2) -> TradePlan | None:
    """Build a concrete trade plan from a `TradeIdea`.

    Returns None when direction is "none" or required fields are missing.
    """
    if idea.direction not in ("long", "short"):
        return None

    last = idea.last_price
    atr_val = idea.atr_value

    if idea.direction == "long":
        # Entry at current price; if inside OB, slightly above OB bottom
        entry = last
        if idea.entry_zone_bottom is not None:
            entry = max(entry, idea.entry_zone_bottom)
        # SL: below OB bottom or last swing low, whichever is wider, with ATR buffer
        sl_base = idea.entry_zone_bottom if idea.entry_zone_bottom is not None else last
        if idea.structure.last_swing_low is not None:
            sl_base = min(sl_base, idea.structure.last_swing_low.price)
        stop_loss = sl_base - atr_val * atr_multiplier
        risk = entry - stop_loss
        if risk <= 0:
            return None
        # TPs: liquidity zones above filtered by minimum R distance, fallback to R multiples
        liq_targets = sorted(
            [z.price for z in idea.liquidity.zones if z.price > entry and z.direction == "buyside"]
        )
        min_r = [1.5, 2.5, 3.5]
        tps: list[float] = []
        used: set[float] = set()
        for min_mult in min_r:
            min_price = entry + risk * min_mult
            picks = [t for t in liq_targets if t >= min_price and t not in used]
            if picks:
                tps.append(picks[0])
                used.add(picks[0])
            else:
                tps.append(min_price)
        rr1 = (tps[0] - entry) / risk
    else:
        entry = last
        if idea.entry_zone_top is not None:
            entry = min(entry, idea.entry_zone_top)
        sl_base = idea.entry_zone_top if idea.entry_zone_top is not None else last
        if idea.structure.last_swing_high is not None:
            sl_base = max(sl_base, idea.structure.last_swing_high.price)
        stop_loss = sl_base + atr_val * atr_multiplier
        risk = stop_loss - entry
        if risk <= 0:
            return None
        liq_targets = sorted(
            [
                z.price
                for z in idea.liquidity.zones
                if z.price < entry and z.direction == "sellside"
            ],
            reverse=True,
        )
        min_r = [1.5, 2.5, 3.5]
        tps = []
        used: set[float] = set()
        for min_mult in min_r:
            max_price = entry - risk * min_mult
            picks = [t for t in liq_targets if t <= max_price and t not in used]
            if picks:
                tps.append(picks[0])
                used.add(picks[0])
            else:
                tps.append(max_price)
        rr1 = (entry - tps[0]) / risk

    return TradePlan(entry=entry, stop_loss=stop_loss, take_profits=tps, rr_to_tp1=rr1)
