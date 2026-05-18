"""Format `Signal` objects into Discord embeds and plain-text reports."""

from __future__ import annotations

import discord

from bot.signals.generator import Signal

ASSET_CLASS_EMOJI = {"crypto": "(crypto)", "forex": "(fx)", "metals": "(gold)"}


def _price_str(price: float) -> str:
    """Format a price with adaptive precision."""
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 10:
        return f"{price:.3f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.6f}"


def embed_for_signal(signal: Signal) -> discord.Embed:
    """Return a `discord.Embed` describing the signal."""
    idea = signal.idea
    plan = signal.plan
    color = discord.Color.green() if idea.direction == "long" else discord.Color.red()
    title = (
        f"{ASSET_CLASS_EMOJI.get(signal.asset_class, '')} {idea.asset} - "
        f"{idea.direction.upper()} | confidence {idea.confidence}/100"
    )
    embed = discord.Embed(title=title, color=color)

    embed.add_field(name="Entry", value=_price_str(plan.entry), inline=True)
    embed.add_field(name="Stop Loss", value=_price_str(plan.stop_loss), inline=True)
    embed.add_field(name="R:R (TP1)", value=f"{plan.rr_to_tp1:.2f}", inline=True)

    tps_str = "\n".join(f"TP{i + 1}: {_price_str(tp)}" for i, tp in enumerate(plan.take_profits))
    embed.add_field(name="Take Profits", value=tps_str, inline=False)

    triggered = [f.name for f in idea.factors if f.triggered]
    embed.add_field(
        name="Confluence",
        value=", ".join(triggered) if triggered else "none",
        inline=False,
    )

    rationale_lines = [f"- {f.name}: {f.detail}" for f in idea.factors if f.triggered]
    if rationale_lines:
        rationale = "\n".join(rationale_lines)
        if len(rationale) > 1000:
            rationale = rationale[:1000] + "..."
        embed.add_field(name="Reasoning", value=rationale, inline=False)

    if idea.fundamental:
        f = idea.fundamental
        fund_lines = [
            f"Sentiment: **{f.sentiment_label}** (score {f.sentiment.score:+.2f})",
        ]
        if f.sentiment.fear_greed is not None:
            fund_lines.append(f"Fear & Greed: **{f.sentiment.fear_greed}/100**")
        if f.red_news_imminent:
            fund_lines.append(f"High-impact news within 2h: {len(f.upcoming_high_impact)} event(s)")
        embed.add_field(name="Fundamentals", value="\n".join(fund_lines), inline=False)

    embed.set_footer(text="Not financial advice. Manage your risk.")
    return embed


def daily_brief_embed(signals: list[Signal]) -> discord.Embed:
    """Compact daily-brief embed listing all active signals."""
    if not signals:
        return discord.Embed(
            title="Daily market brief",
            description="No high-confidence setups today. Stay patient.",
            color=discord.Color.blurple(),
        )
    embed = discord.Embed(
        title=f"Daily market brief - {len(signals)} setup(s)",
        description="Detailed signals follow below.",
        color=discord.Color.blurple(),
    )
    for s in signals:
        embed.add_field(
            name=f"{s.idea.asset} - {s.idea.direction.upper()}",
            value=f"Confidence {s.idea.confidence}/100, R:R {s.plan.rr_to_tp1:.2f}",
            inline=False,
        )
    return embed
