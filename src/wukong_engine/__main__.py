import logging
from argparse import ArgumentParser
from pathlib import Path

from .pipeline import execute_pipeline
from .utils.text_utils import remove_sentence_dot

### Logging Configuration ###


# Custom logging formatter
class LevelBasedFormatter(logging.Formatter):
    def __init__(self, format_map, default_format):
        super().__init__()
        self.format_map = format_map
        self.default_format = default_format

    def format(self, record):
        # Set the format based on the log level
        format_str = self.format_map.get(record.levelno, self.default_format)
        self._style._fmt = format_str
        return super().format(record)


# Logging formats for different levels
level_formats = {
    logging.WARNING: '[WARNING] %(message)s',
    logging.ERROR: '[ERROR] Error: %(message)s',
    logging.CRITICAL: '[CRITICAL] Error: %(message)s',
    logging.DEBUG: '[DEBUG] %(message)s',
}
default_format = '%(message)s'

# Logging Handler
handler = logging.StreamHandler()  # Outputs to console (stdout/stderr)
handler.setFormatter(LevelBasedFormatter(level_formats, default_format))

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
        prog='wukong_engine', description='Engine for constructing knowledge graphs from unstructured documents.'
    )
    parser.add_argument(
        'data_dir',
        type=Path,
        help='Path to the directory containing the data (e.g. data/example)',
    )

    # Parse command line arguments
    args = parser.parse_args()

    # Check if data directory exists
    if not args.data_dir.exists():
        logger.critical(f'Data directory "{args.data_dir}" does not exist.')
        return

    # Execute the pipeline
    try:
        execute_pipeline(args.data_dir)
    except Exception as error:
        logger.critical(f'{remove_sentence_dot(str(error))}.')


# Execute WUKONG engine
if __name__ == '__main__':
    main()
