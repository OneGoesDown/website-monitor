"""Logging configuration for Website Monitor.

Produces a single consistent, timestamped log format across both
the console and the rotating log file, replacing the old mix of
plain `print()` calls and hand-written log lines.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

import config


def setup_logging() -> logging.Logger:
    """Configure and return the application logger.

    Safe to call multiple times (e.g. from tests) without duplicating
    handlers.
    """
    log_dir = os.path.dirname(config.LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("website_monitor")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
