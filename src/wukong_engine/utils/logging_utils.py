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
    def __init__(self, format_map: dict[int, str], default_format: str) -> None:
        super().__init__()
        self.default_formatter = logging.Formatter(default_format)
        self.formatters = {level: logging.Formatter(fmt) for level, fmt in format_map.items()}

    def format(self, record: logging.LogRecord) -> str:
        formatter = self.formatters.get(record.levelno, self.default_formatter)
        return formatter.format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Set up global logging configuration.

    Args:
        level: The logging level to set for the root logger. Defaults to logging.INFO.
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
