import logging
from argparse import ArgumentParser
from pathlib import Path

from .pipeline import execute_pipeline

### Logging Configuration ###


# Custom logging formatter
class LevelFormatter(logging.Formatter):
    def __init__(self, format_map: dict[int, str], default_format: str) -> None:
        super().__init__()
        self.default_formatter = logging.Formatter(default_format)
        self.formatters = {level: logging.Formatter(fmt) for level, fmt in format_map.items()}

    def format(self, record: logging.LogRecord) -> str:
        formatter = self.formatters.get(record.levelno, self.default_formatter)
        return formatter.format(record)


# Logging formats for different levels
level_formats = {
    logging.WARNING: '[WARNING] %(message)s',
    logging.ERROR: '[ERROR] %(message)s',
    logging.CRITICAL: '[CRITICAL_ERROR] %(message)s',
    logging.DEBUG: '[DEBUG] %(message)s',
}
default_format = '%(message)s'

# Logging Handler
handler = logging.StreamHandler()  # Outputs to console (stdout/stderr)
handler.setFormatter(LevelFormatter(level_formats, default_format))

# Root Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Module Loggers
logging.getLogger('wukong_engine.extraction.data_processing').setLevel(logging.DEBUG)

# Third Party Loggers
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)


def main() -> None:
    """
    Entry point for the WUKONG engine.
    """
    # Define command line arguments
    parser = ArgumentParser(
        prog='wukong_engine',
        description='Engine for constructing knowledge graphs from unstructured documents.',
    )
    parser.add_argument('data_dir', type=Path, help='Path to the directory containing the data (e.g. data/example)')

    # Parse command line arguments
    args = parser.parse_args()

    # Check if data directory exists
    if not args.data_dir.exists():
        logger.critical(f'Data directory "{args.data_dir}" does not exist.')
        return

    # Execute the pipeline
    try:
        execute_pipeline(args.data_dir)
    except (ValueError, FileNotFoundError) as error:
        logger.critical(f'{str(error).removesuffix(".")}.')
    except Exception:
        logger.exception('An unexpected error occurred during pipeline execution.')


# Execute WUKONG engine
if __name__ == '__main__':
    main()
