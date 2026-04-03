"""Structured logging configuration."""

import logging
import sys

from app.core.settings import settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s  %(message)s"


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        for existing in root_logger.handlers:
            existing.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))
            existing.setLevel(level)
