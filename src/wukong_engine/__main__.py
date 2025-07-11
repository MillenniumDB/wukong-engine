"""The main entry point for executing the WUKONG engine.

This module is executed as a script and handles:
    - Parsing command-line arguments
    - Initializing the logging configuration
    - Validating the input data directory
    - Running the engine pipeline

Example:
    python -m wukong_engine data/example --config config/default.toml
"""

import logging
import sys
from argparse import ArgumentParser
from pathlib import Path

from .core.pipeline import execute_pipeline
from .utils.logging_utils import setup_logging

# Logging
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize the engine and execute the main pipeline."""
    # Define command line arguments
    parser = ArgumentParser(
        prog='wukong_engine',
        description='Engine for constructing knowledge graphs from unstructured documents, using the power of LLMs.',
    )
    parser.add_argument(
        'data_dir',
        type=Path,
        help='Path to the directory containing the data (e.g. data/example)',
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path('./config/default.toml'),
        help='Path to the engine configuration file (e.g. config/default.toml)',
        metavar='CONFIG_FILE',
    )

    # Parse command line arguments
    args = parser.parse_args()

    # Set up global logging
    setup_logging(level=logging.INFO)
    logger.info('Starting WUKONG Engine...')

    # Execute the pipeline
    try:
        execute_pipeline(args.data_dir, args.config)
    except (FileNotFoundError, ValueError) as error:
        logger.critical(f'{str(error).removesuffix(".")}.')
        sys.exit(1)
    except Exception:
        logger.exception('An unexpected error occurred during pipeline execution.')
        sys.exit(1)


# Execute the WUKONG engine
if __name__ == '__main__':
    main()
