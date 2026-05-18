"""APScheduler jobs: daily 07:00 brief + session-open signals."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import get_settings
from bot.data import BinanceClient, NewsClient, TwelveDataClient
from bot.discord_client import TradingBot
from bot.signals.generator import generate_all_signals
from bot.utils.logger import logger


async def _daily_brief_job(
    bot: TradingBot, binance: BinanceClient, td: TwelveDataClient, news: NewsClient
) -> None:
    logger.info("Running daily-brief job")
    signals = await generate_all_signals(binance, td, news)
    await bot.post_daily_brief(signals)


async def _session_job(
    session: str,
    bot: TradingBot,
    binance: BinanceClient,
    td: TwelveDataClient,
    news: NewsClient,
) -> None:
    logger.info(f"Running session-open job: {session}")
    signals = await generate_all_signals(binance, td, news)
    await bot.post_session_summary(session, signals)


def schedule_jobs(
    bot: TradingBot, binance: BinanceClient, td: TwelveDataClient, news: NewsClient
) -> AsyncIOScheduler:
    """Build and return an `AsyncIOScheduler` with all jobs configured."""
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    # Daily local brief
    scheduler.add_job(
        _daily_brief_job,
        CronTrigger(
            hour=settings.daily_report_hour,
            minute=settings.daily_report_minute,
            timezone=settings.timezone,
        ),
        args=(bot, binance, td, news),
        id="daily_brief",
        replace_existing=True,
        misfire_grace_time=600,
    )
    # Session opens (UTC)
    for session, (hour, minute) in (
        ("asia", (0, 0)),
        ("london", (7, 0)),
        ("new_york", (12, 0)),
    ):
        scheduler.add_job(
            _session_job,
            CronTrigger(hour=hour, minute=minute, timezone="UTC"),
            args=(session, bot, binance, td, news),
            id=f"session_{session}",
            replace_existing=True,
            misfire_grace_time=600,
        )
    return scheduler
