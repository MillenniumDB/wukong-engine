"""Provides utilities for logging configuration.

This module defines functions and classes to set up
and manage the logging system of the engine.

Functions:
    setup_logging: Configures the global logging settings.
"""

import logging

# Logging formats
LEVEL_FORMATS = {
    logging.WARNING: '[WARNING] %(message)s',
    logging.ERROR: '[ERROR] %(message)s',
    logging.CRITICAL: '[CRITICAL_ERROR] %(message)s',
    logging.DEBUG: '[DEBUG] %(message)s',
}
DEFAULT_FORMAT = '%(message)s'


class LevelFormatter(logging.Formatter):
    """A custom log formatter that applies different formats based on the log severity level."""

    def __init__(self, format_map: dict[int, str], default_format: str) -> None:
        """Initialize the log formatter with specific formats for different log levels.

        Args:
            format_map: A dictionary mapping log levels to their respective format strings.
            default_format: The default format string to use for log levels not specified in `format_map`.
        """
        super().__init__()
        self._default_formatter = logging.Formatter(default_format)
        self._formatters = {level: logging.Formatter(fmt) for level, fmt in format_map.items()}

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record based on its severity level.

        Args:
            record: The log record to format.

        Returns:
            A formatted log message based on the severity level of the record.
        """
        formatter = self._formatters.get(record.levelno, self._default_formatter)
        return formatter.format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Set up global logging configuration.

    Configures the root logger and sets up handlers for different log severity levels.
    Manages third-party loggers to adjust their verbosity.

    Args:
        level: The base logging level to set for the root logger.
    """
    # Logging Handler
    handler = logging.StreamHandler()  # Outputs to console (stdout/stderr)
    handler.setFormatter(LevelFormatter(LEVEL_FORMATS, DEFAULT_FORMAT))

    # Root Logger
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(handler)

    # Module Loggers
    logging.getLogger('wukong_engine.extraction.data_processing').setLevel(logging.DEBUG)

    # Third Party Loggers
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
