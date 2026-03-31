"""Logging configuration for JARVIS.

Uses loguru for structured logging with file and console output.
"""

import sys
from pathlib import Path
from typing import Any

from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: str | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """Configure the global logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, logs to console only.
        rotation: Log file rotation size/time
        retention: How long to keep old log files
    """
    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
        )

    logger.info(f"Logger initialized with level={level}")


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance.

    Args:
        name: Optional logger name for context

    Returns:
        Logger instance bound with name context
    """
    if name:
        return logger.bind(name=name)
    return logger


# Convenience exports
__all__ = ["setup_logger", "get_logger", "logger"]
