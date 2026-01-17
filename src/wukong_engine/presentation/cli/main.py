"""The main entry point for executing the WUKONG CLI.

This module is executed as a script and handles:
    - Parsing command-line arguments
    - Initializing the engine
    - Running the engine pipeline

Example:
    poetry run wukong data/example --config config/default.toml
"""

import argparse
import logging
import sys
from pathlib import Path

from wukong_engine.bootstrap.cli import CliApplication
from wukong_engine.infrastructure.logging import configure_logging

# Logging
logger = logging.getLogger(__name__)


def print_error(message: str) -> None:
    """Print a formatted error message to stderr.

    Args:
        message: The error message to print.
    """
    message = message.rstrip()
    if message and message[-1] not in '.!?':
        message += '.'
    print(f'Error: {message}', file=sys.stderr)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the WUKONG CLI.

    Returns:
        A Namespace object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog='wukong',
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
    parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
    )
    return parser.parse_args()


def main() -> None:
    """Run the WUKONG CLI."""
    # Parse command line arguments
    args = parse_args()

    # Configure logging
    log_level = logging.WARNING if args.verbose == 0 else logging.INFO if args.verbose == 1 else logging.DEBUG
    configure_logging(level=log_level)

    # Create CLI app
    app = CliApplication()

    # Execute the pipeline
    print('Starting WUKONG...')
    try:
        app.graph_construction.execute(data_dir=args.data_dir, config_path=args.config)
        print('WUKONG pipeline execution completed!')
    except (FileNotFoundError, ValueError, TypeError) as error:
        logger.exception('Failed to process input.')
        print_error(str(error))
        sys.exit(1)
    except Exception:
        logger.exception('Unhandled exception.')
        print('Error: An unexpected error occurred.', file=sys.stderr)
        sys.exit(1)


# Execute the WUKONG engine CLI
if __name__ == '__main__':
    main()
