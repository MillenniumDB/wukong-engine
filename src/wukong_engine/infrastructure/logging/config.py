"""Provides utilities for logging configuration.

This module defines functions to configure and manage the logging system of the engine.
"""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Set up global logging configuration.

    Configures the root logger for different log severity levels.
    Manages third-party loggers to adjust their verbosity.

    Args:
        level: The base logging level to set for the root logger.
    """
    # Root Logger
    logging.basicConfig(level=level, format='[%(levelname)s] %(name)s: %(message)s')

    # Third Party Loggers
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
