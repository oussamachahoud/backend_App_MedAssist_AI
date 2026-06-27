"""
app/core/logging.py
Structured logging configuration using loguru.
Sets up request-level context and JSON-compatible output.
"""

import sys
from loguru import logger


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure loguru for the application.

    Args:
        log_level: Minimum log level (DEBUG | INFO | WARNING | ERROR | CRITICAL)
    """
    # Remove default handler
    logger.remove()

    # Console handler — human-friendly format in development
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # File handler — JSON-style for production log aggregators
    logger.add(
        "logs/api.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=False,  # Disable in prod to avoid leaking values
        enqueue=True,    # Thread-safe async logging
    )

    logger.info(f"Logging initialised at level: {log_level}")
