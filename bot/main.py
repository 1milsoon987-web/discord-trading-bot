"""Entry point: `python -m bot.main [--dry-run] [--once]`."""

from __future__ import annotations

import argparse
import asyncio
import json

from bot.config import get_settings
from bot.data import BinanceClient, NewsClient, TwelveDataClient
from bot.discord_client import TradingBot
from bot.scheduler import schedule_jobs
from bot.signals.generator import generate_all_signals
from bot.utils.logger import logger, setup_logging


def _signal_to_dict(sig) -> dict:
    idea = sig.idea
    plan = sig.plan
    return {
        "asset": idea.asset,
        "asset_class": sig.asset_class,
        "direction": idea.direction,
        "confidence": idea.confidence,
        "entry": plan.entry,
        "stop_loss": plan.stop_loss,
        "take_profits": plan.take_profits,
        "rr_to_tp1": plan.rr_to_tp1,
        "factors_triggered": [f.name for f in idea.factors if f.triggered],
        "factors_all": [
            {"name": f.name, "weight": f.weight, "triggered": f.triggered, "detail": f.detail}
            for f in idea.factors
        ],
        "fundamental": {
            "sentiment_label": idea.fundamental.sentiment_label if idea.fundamental else None,
            "sentiment_score": idea.fundamental.sentiment.score if idea.fundamental else None,
            "fear_greed": (idea.fundamental.sentiment.fear_greed if idea.fundamental else None),
            "red_news_imminent": (
                idea.fundamental.red_news_imminent if idea.fundamental else False
            ),
        },
    }


async def run_once(dry_run: bool) -> None:
    """Run a single signal generation pass and either post or print results."""
    binance = BinanceClient()
    td = TwelveDataClient()
    news = NewsClient()
    try:
        signals = await generate_all_signals(binance, td, news)
        logger.info(f"Generated {len(signals)} signal(s)")
        if dry_run:
            print(json.dumps([_signal_to_dict(s) for s in signals], indent=2))
            return
        bot = TradingBot()

        async def runner() -> None:
            await bot.wait_until_ready()
            await bot.post_daily_brief(signals)
            await bot.close()

        async with bot:
            asyncio.create_task(runner())  # noqa: RUF006
            await bot.start(bot.settings.discord_bot_token)
    finally:
        await binance.close()
        await td.close()
        await news.close()


async def run_forever() -> None:
    """Run the bot indefinitely with scheduled jobs."""
    settings = get_settings()
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set")
    binance = BinanceClient()
    td = TwelveDataClient()
    news = NewsClient()
    bot = TradingBot()
    scheduler = schedule_jobs(bot, binance, td, news)

    async def on_ready_hook() -> None:
        scheduler.start()
        logger.info("Scheduler started")

    bot.add_listener(on_ready_hook, "on_ready")

    try:
        await bot.start(settings.discord_bot_token)
    finally:
        scheduler.shutdown(wait=False)
        await binance.close()
        await td.close()
        await news.close()


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Discord trading-signal bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print signals to stdout instead of posting to Discord",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate signals once and exit (skip scheduling)",
    )
    args = parser.parse_args()

    setup_logging()

    if args.once or args.dry_run:
        asyncio.run(run_once(dry_run=args.dry_run))
    else:
        asyncio.run(run_forever())


if __name__ == "__main__":
    main()
