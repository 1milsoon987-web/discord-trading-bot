"""Loguru-based logging helpers."""

from __future__ import annotations

import sys

from loguru import logger

from bot.config import get_settings


def setup_logging() -> None:
    """Configure the global loguru logger from settings."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=get_settings().log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )


__all__ = ["logger", "setup_logging"]
