"""
DocSync Logging Configuration

Structured logging with both file and console handlers.
"""

import os
import logging
from datetime import datetime


def setup_logging(log_dir: str = "./data/logs", level: int = logging.INFO):
    """Configure structured logging for the entire application"""

    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(
        log_dir, f"docsync_{datetime.now().strftime('%Y%m%d')}.log"
    )

    # Root logger
    root_logger = logging.getLogger("docsync")
    root_logger.setLevel(level)

    # Avoid duplicate handlers
    if root_logger.handlers:
        return root_logger

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    )
    file_handler.setFormatter(file_fmt)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger
