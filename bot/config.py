"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    All values can be overridden via environment variables or a `.env` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Discord
    discord_bot_token: str = Field(default="", description="Discord bot token")
    discord_signal_channel_id: int = Field(default=0, description="Channel ID for signals")

    # Data providers
    twelvedata_api_key: str = Field(default="", description="TwelveData API key (free tier ok)")
    binance_api_key: str = Field(default="", description="Optional Binance API key")
    binance_api_secret: str = Field(default="", description="Optional Binance API secret")
    news_api_key: str = Field(default="", description="Optional NewsAPI key")

    # Behavior
    timezone: str = Field(default="Africa/Casablanca")
    daily_report_hour: int = Field(default=7, ge=0, le=23)
    daily_report_minute: int = Field(default=0, ge=0, le=59)

    # Risk
    default_risk_percent: float = Field(default=1.0, ge=0.1, le=5.0)
    min_confidence_score: int = Field(default=65, ge=0, le=100)

    # Watchlist
    crypto_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    forex_symbols: list[str] = Field(default_factory=lambda: ["EUR/USD", "GBP/USD", "USD/JPY"])
    metals_symbols: list[str] = Field(default_factory=lambda: ["XAU/USD"])

    # Logging
    log_level: str = Field(default="INFO")

    # Dev
    dry_run: bool = Field(default=False)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
