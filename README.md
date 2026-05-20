# Discord Trading Signal Bot

Multi-asset (Crypto + Forex + Gold) Discord bot that posts trading signals using a
confluence engine that combines **Smart Money Concepts** (Order Blocks, Fair Value Gaps,
Liquidity Sweeps, Market Structure / BOS / CHoCH), classical indicators (RSI, EMA, ATR),
and **fundamental analysis** (economic calendar, news sentiment, Fear & Greed index).

> **Honesty disclaimer:** No algorithm guarantees a "60%+ win rate". This bot produces
> *high-quality, well-reasoned* signals; profitability depends on market conditions and
> *your* risk management. Do not trade more than you can afford to lose.

## Features

- **Daily market briefing** at 07:00 (configurable timezone, default `Africa/Casablanca`)
- **Session-open signals** at the opens of Asia (00:00 UTC), London (07:00 UTC), New York (12:00 UTC)
- **Multi-asset coverage:** BTC, ETH, SOL, EUR/USD, GBP/USD, USD/JPY, XAU/USD (Gold)
- **Confluence scoring engine** — each signal requires at least N independent confirmations
- **Risk-managed output:** Entry, Stop Loss, 3× Take Profit, Risk:Reward, lot/position size hint
- **Reasoning in every signal:** technical + fundamental rationale
- **Dry-run mode** for testing without posting

## Quick start

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env and put your DISCORD_BOT_TOKEN, channel ID, TwelveData key

# 3. Smoke test (no Discord, prints signals to stdout)
python -m bot.main --dry-run --once

# 4. Run for real (persistent bot mode)
python -m bot.main

# 5. Alternative: post once via webhook (used by GitHub Actions cron)
python -m bot.main --webhook --label "Manual run"
```

## Hosting with GitHub Actions (free, no card)

The repository ships with `.github/workflows/signals.yml`. It runs every Asia /
London / New York session open plus the daily Casablanca brief and posts to a
Discord webhook — no always-on server needed.

1. In Discord, **Channel Settings → Integrations → Webhooks → New Webhook**
   and copy the URL.
2. In GitHub, **Settings → Secrets and variables → Actions** and add:
   - `DISCORD_WEBHOOK_URL` (required)
   - `TWELVEDATA_API_KEY` (optional, enables FX/metals)
3. Trigger a one-off run from the **Actions** tab → *Trading signals* →
   *Run workflow* to confirm the wiring before scheduled runs kick in.

## Architecture

```
bot/
├── main.py               # entrypoint, wires everything
├── config.py             # pydantic-settings loader
├── scheduler.py          # APScheduler jobs (daily 07:00 + session opens)
├── discord_client.py     # discord.py bot
├── data/                 # exchange / API adapters
│   ├── binance.py        # crypto klines (public)
│   ├── twelvedata.py     # forex + gold
│   └── news.py           # RSS news, F&G index, economic calendar
├── analysis/
│   ├── structure.py      # swing highs/lows, BOS, CHoCH
│   ├── orderblocks.py    # bullish/bearish OBs
│   ├── fvg.py            # fair value gaps
│   ├── liquidity.py      # liquidity sweeps / equal highs-lows
│   ├── indicators.py     # ATR, RSI, EMA, divergence
│   ├── fundamental.py    # sentiment, F&G, news, calendar
│   └── engine.py         # confluence scoring + signal decision
├── signals/
│   ├── generator.py
│   ├── risk.py           # SL/TP placement using ATR + structure
│   └── formatter.py      # Discord embeds
└── utils/
    ├── logger.py
    └── timezone.py
```

## Strategy summary

For each asset we compute a **bias** on the higher timeframe (4H/1D) using market
structure (BOS/CHoCH) and trend filters. We then look for **entry confluence** on the
lower timeframe (15m/1H):

1. Price tagging a fresh unmitigated **Order Block** aligned with HTF bias
2. Presence of an **Imbalance / Fair Value Gap** to fill
3. Recent **liquidity sweep** (taking out equal highs/lows or session high/low)
4. **RSI divergence** or EMA-50/EMA-200 alignment as a confirmation
5. **Fundamental filter:** no high-impact red news within ±30 minutes; sentiment not contradictory

Each item contributes to a **confidence score (0–100)**. Only signals at or above
`MIN_CONFIDENCE_SCORE` (default 65) are published. Stop loss is placed beyond the
sweeping wick / order block; take profits are placed at the next 3 liquidity pools or
structural levels with a minimum 1:2 R:R on TP1.

## Deployment

Any host that can run a Python 3.11+ process 24/7 works. Recommended: Railway, Render
free-tier worker, or any VPS. Docker support coming next.

## License

MIT
