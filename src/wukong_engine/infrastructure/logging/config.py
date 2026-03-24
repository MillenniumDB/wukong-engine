"""Provides utilities for logging configuration.

This module defines functions to configure and manage the logging system of the engine.
"""

import logging


def configure_logging(verbosity: int) -> None:
    """Set up global logging configuration.

    Configures the root logger for different log severity levels.
    Manages third-party loggers to adjust their verbosity.

    Args:
        verbosity: The verbosity level (0 for WARNING, 1 for INFO, 2 or more for DEBUG).
    """
    # Root Logger
    level = _map_verbosity_to_level(verbosity)
    logging.basicConfig(level=level, format='[%(levelname)s] %(name)s: %(message)s')

    # Third Party Loggers
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def _map_verbosity_to_level(verbosity: int) -> int:
    """Map a verbosity count to a logging level."""
    if verbosity <= 0:
        return logging.WARNING
    if verbosity == 1:
        return logging.INFO
    return logging.DEBUG
