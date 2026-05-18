"""Discord bot wiring."""

from __future__ import annotations

import discord
from discord.ext import commands

from bot.config import get_settings
from bot.signals.formatter import daily_brief_embed, embed_for_signal
from bot.signals.generator import Signal
from bot.utils.logger import logger


class TradingBot(commands.Bot):
    """Discord bot for posting trading signals."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = False  # we only post; we don't read messages
        super().__init__(command_prefix="!", intents=intents)
        self.settings = get_settings()

    async def on_ready(self) -> None:
        logger.info(f"Discord connected as {self.user} (id={self.user.id if self.user else '?'})")

    async def _signal_channel(self) -> discord.abc.Messageable | None:
        channel_id = self.settings.discord_signal_channel_id
        if channel_id == 0:
            logger.warning("DISCORD_SIGNAL_CHANNEL_ID is not set; cannot post")
            return None
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            logger.error(f"Channel {channel_id} is not messageable")
            return None
        return channel

    async def post_daily_brief(self, signals: list[Signal]) -> None:
        channel = await self._signal_channel()
        if channel is None:
            return
        await channel.send(embed=daily_brief_embed(signals))
        for sig in signals:
            await channel.send(embed=embed_for_signal(sig))

    async def post_signal(self, signal: Signal) -> None:
        channel = await self._signal_channel()
        if channel is None:
            return
        await channel.send(embed=embed_for_signal(signal))

    async def post_session_summary(self, session: str, signals: list[Signal]) -> None:
        channel = await self._signal_channel()
        if channel is None:
            return
        if not signals:
            await channel.send(
                embed=discord.Embed(
                    title=f"{session.title()} session open - no setups",
                    description="No qualifying confluence detected.",
                    color=discord.Color.blurple(),
                )
            )
            return
        intro = discord.Embed(
            title=f"{session.title()} session open - {len(signals)} setup(s)",
            color=discord.Color.gold(),
        )
        await channel.send(embed=intro)
        for s in signals:
            await channel.send(embed=embed_for_signal(s))
