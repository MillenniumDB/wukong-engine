"""The main entry point for executing the WUKONG CLI.

This module is executed as a script and handles:
    - Parsing command-line arguments
    - Initializing the engine
    - Running the engine pipeline

Example:
    python -m wukong_engine/presentation/cli/main.py data/example --config config/default.toml
"""

import logging
import sys
from argparse import ArgumentParser
from pathlib import Path

# from wukong_engine.app.workflows.build_graph import execute_pipeline
# from wukong_engine.bootstrap.cli import create_cli_app

# Logging
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize the WUKONG CLI."""
    # Define command line arguments
    parser = ArgumentParser(
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

    # Parse command line arguments
    args = parser.parse_args()

    # Execute the pipeline
    print('Starting WUKONG Engine...')
    try:
        # execute_pipeline(args.data_dir, args.config)
        print('PIPELINE')
    except (FileNotFoundError, ValueError, TypeError) as error:
        print(f'{str(error).removesuffix(".")}.', file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('An unexpected error occurred.', file=sys.stderr)
        logger.exception('Unhandled exception')
        sys.exit(1)


# Execute the WUKONG engine CLI
if __name__ == '__main__':
    main()
