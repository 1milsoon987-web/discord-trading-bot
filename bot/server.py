"""FastAPI wrapper that hosts the Discord bot + scheduler for Fly.io deployment.

Exports `app` (FastAPI). Inside the lifespan it boots the Discord client and
APScheduler. A `/health` endpoint allows Fly.io's healthchecks to confirm the
process is up.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import pytz
from fastapi import FastAPI

from bot.config import get_settings
from bot.data import BinanceClient, NewsClient, TwelveDataClient
from bot.discord_client import TradingBot
from bot.scheduler import schedule_jobs
from bot.signals.generator import generate_all_signals
from bot.utils.logger import logger, setup_logging

# Module-level state mutated inside lifespan
_state: dict[str, Any] = {
    "bot_task": None,
    "scheduler": None,
    "started_at": None,
    "last_run_at": None,
    "last_signal_count": None,
    "bot": None,
    "binance": None,
    "td": None,
    "news": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot Discord bot + scheduler on startup, shut them down on exit."""
    setup_logging()
    settings = get_settings()

    binance = BinanceClient()
    td = TwelveDataClient()
    news = NewsClient()
    bot = TradingBot()
    scheduler = schedule_jobs(bot, binance, td, news)

    _state.update(
        {
            "binance": binance,
            "td": td,
            "news": news,
            "bot": bot,
            "scheduler": scheduler,
            "started_at": datetime.now(tz=pytz.UTC).isoformat(),
        }
    )

    async def _run_bot() -> None:
        try:
            scheduler.start()
            logger.info("Scheduler started")
            await bot.start(settings.discord_bot_token)
        except Exception as e:
            logger.exception(f"Discord bot crashed: {e}")

    if settings.discord_bot_token:
        _state["bot_task"] = asyncio.create_task(_run_bot())
        logger.info("Discord bot task spawned")
    else:
        logger.warning("DISCORD_BOT_TOKEN is not set; serving health endpoint only")

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        if _state["bot_task"] is not None:
            await bot.close()
            _state["bot_task"].cancel()
        await binance.close()
        await td.close()
        await news.close()


app = FastAPI(
    title="Discord Trading Bot",
    description="Health & control surface for the trading-signal Discord bot",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "discord-trading-bot",
        "status": "ok",
        "started_at": _state["started_at"],
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    bot = _state.get("bot")
    return {
        "status": "ok",
        "discord_ready": bool(bot and bot.is_ready()) if bot else False,
        "scheduler_running": bool(_state["scheduler"] and _state["scheduler"].running),
    }


@app.get("/status")
async def status() -> dict[str, Any]:
    settings = get_settings()
    scheduler = _state.get("scheduler")
    jobs: list[dict[str, Any]] = []
    if scheduler is not None:
        for job in scheduler.get_jobs():
            next_run = getattr(job, "next_run_time", None)
            jobs.append(
                {
                    "id": job.id,
                    "next_run": next_run.isoformat() if next_run else None,
                }
            )
    return {
        "timezone": settings.timezone,
        "daily_report_hour": settings.daily_report_hour,
        "min_confidence_score": settings.min_confidence_score,
        "crypto_symbols": settings.crypto_symbols,
        "forex_symbols": settings.forex_symbols,
        "metals_symbols": settings.metals_symbols,
        "started_at": _state["started_at"],
        "last_run_at": _state["last_run_at"],
        "last_signal_count": _state["last_signal_count"],
        "scheduled_jobs": jobs,
    }


@app.post("/run-now")
async def run_now() -> dict[str, Any]:
    """Manually trigger a signal evaluation pass (useful for testing)."""
    bot: TradingBot | None = _state.get("bot")
    binance: BinanceClient | None = _state.get("binance")
    td: TwelveDataClient | None = _state.get("td")
    news: NewsClient | None = _state.get("news")
    if not (bot and binance and td and news):
        return {"ok": False, "error": "bot not initialised yet"}
    signals = await generate_all_signals(binance, td, news)
    _state["last_run_at"] = datetime.now(tz=pytz.UTC).isoformat()
    _state["last_signal_count"] = len(signals)
    if bot.is_ready():
        await bot.post_daily_brief(signals)
    return {
        "ok": True,
        "signals_generated": len(signals),
        "posted_to_discord": bot.is_ready(),
        "details": [
            {
                "asset": s.idea.asset,
                "direction": s.idea.direction,
                "confidence": s.idea.confidence,
            }
            for s in signals
        ],
    }
