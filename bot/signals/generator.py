"""Generate trade signals for the watchlist."""

from __future__ import annotations

from dataclasses import dataclass

from bot.analysis.engine import TradeIdea, evaluate
from bot.analysis.fundamental import collect_fundamental
from bot.config import get_settings
from bot.data import BinanceClient, NewsClient, TwelveDataClient
from bot.signals.risk import TradePlan, build_plan
from bot.utils.logger import logger


@dataclass(slots=True)
class Signal:
    """Full signal ready for output."""

    idea: TradeIdea
    plan: TradePlan
    asset_class: str

    @property
    def confidence(self) -> int:
        return self.idea.confidence

    @property
    def direction(self) -> str:
        return self.idea.direction


HTF_INTERVAL_BINANCE = "4h"
LTF_INTERVAL_BINANCE = "1h"
HTF_INTERVAL_TD = "4h"
LTF_INTERVAL_TD = "1h"


async def _evaluate_crypto(symbol: str, binance: BinanceClient, news: NewsClient) -> TradeIdea:
    df_htf = await binance.klines(symbol, HTF_INTERVAL_BINANCE, limit=300)
    df_ltf = await binance.klines(symbol, LTF_INTERVAL_BINANCE, limit=300)
    fundamental = await collect_fundamental(symbol, "crypto", news)
    return evaluate(symbol, df_htf, df_ltf, fundamental=fundamental)


async def _evaluate_td(
    symbol: str, asset_class: str, td: TwelveDataClient, news: NewsClient
) -> TradeIdea:
    df_htf = await td.time_series(symbol, HTF_INTERVAL_TD, outputsize=300)
    df_ltf = await td.time_series(symbol, LTF_INTERVAL_TD, outputsize=300)
    fundamental = await collect_fundamental(symbol, asset_class, news)
    return evaluate(symbol, df_htf, df_ltf, fundamental=fundamental)


async def generate_all_signals(
    binance: BinanceClient, td: TwelveDataClient, news: NewsClient
) -> list[Signal]:
    """Evaluate every watchlist symbol and return signals that meet the threshold."""
    settings = get_settings()
    min_conf = settings.min_confidence_score
    signals: list[Signal] = []

    for symbol in settings.crypto_symbols:
        try:
            idea = await _evaluate_crypto(symbol, binance, news)
        except Exception as e:
            logger.warning(f"Crypto eval failed for {symbol}: {e}")
            continue
        if idea.direction == "none" or idea.confidence < min_conf:
            logger.info(f"{symbol}: skipped (dir={idea.direction} conf={idea.confidence})")
            continue
        plan = build_plan(idea)
        if plan is None:
            continue
        signals.append(Signal(idea=idea, plan=plan, asset_class="crypto"))

    for symbol in settings.forex_symbols:
        try:
            idea = await _evaluate_td(symbol, "forex", td, news)
        except Exception as e:
            logger.warning(f"Forex eval failed for {symbol}: {e}")
            continue
        if idea.direction == "none" or idea.confidence < min_conf:
            logger.info(f"{symbol}: skipped (dir={idea.direction} conf={idea.confidence})")
            continue
        plan = build_plan(idea)
        if plan is None:
            continue
        signals.append(Signal(idea=idea, plan=plan, asset_class="forex"))

    for symbol in settings.metals_symbols:
        try:
            idea = await _evaluate_td(symbol, "metals", td, news)
        except Exception as e:
            logger.warning(f"Metals eval failed for {symbol}: {e}")
            continue
        if idea.direction == "none" or idea.confidence < min_conf:
            logger.info(f"{symbol}: skipped (dir={idea.direction} conf={idea.confidence})")
            continue
        plan = build_plan(idea)
        if plan is None:
            continue
        signals.append(Signal(idea=idea, plan=plan, asset_class="metals"))

    return signals
