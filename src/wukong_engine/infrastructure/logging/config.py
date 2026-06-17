"""Provides utilities for logging configuration.

This module defines functions to configure and manage the logging system of the engine.
"""

import logging


def _map_verbosity_to_level(verbosity: int) -> int:
    """Map a verbosity count to a logging level."""
    if verbosity <= 0:
        return logging.WARNING
    if verbosity == 1:
        return logging.INFO
    return logging.DEBUG


def configure_logging(verbosity: int) -> None:
    """Set up global logging configuration.

    Configures the root logger for different log severity levels.
    Manages third-party loggers to adjust their verbosity.

    Args:
        verbosity: The verbosity level (0 for WARNING, 1 for INFO, 2 or more for DEBUG).
    """
    # Root
    level = _map_verbosity_to_level(verbosity)
    logging.basicConfig(level=level, format='[%(levelname)s] %(name)s → %(message)s')

    # Asyncio
    logging.getLogger('asyncio').setLevel(logging.ERROR)

    # Hugging Face
    logging.getLogger('huggingface_hub').setLevel(logging.ERROR)
    logging.getLogger('transformers').setLevel(logging.ERROR)
    logging.getLogger('httpcore').setLevel(logging.ERROR)

    # OpenAI
    logging.getLogger('openai').setLevel(logging.ERROR)
    logging.getLogger('httpx').setLevel(logging.ERROR)


def set_logger_verbosity(verbosity: int, logger_name: str | None = None) -> None:
    """Set desired verbosity for a specific logger.

    If no logger name is provided, verbosity will be set for the root logger.

    Args:
        verbosity: The verbosity level (0 for WARNING, 1 for INFO, 2 or more for DEBUG).
        logger_name: The name of the logger to configure.
    """
    level = _map_verbosity_to_level(verbosity)
    if logger_name is None:
        logging.getLogger().setLevel(level)
    else:
        logging.getLogger(logger_name).setLevel(level)


# Default to WARNING level at initialization
configure_logging(verbosity=0)
