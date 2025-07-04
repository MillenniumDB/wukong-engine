import logging
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
    parser.add_argument('data_dir', type=Path, help='Path to the directory containing the data (e.g. data/example)')

    # Parse command line arguments
    args = parser.parse_args()

    # Set up global logging
    setup_logging(level=logging.INFO)
    logger.info('Starting WUKONG Engine...')

    # Check if data directory exists
    if not args.data_dir.exists():
        logger.critical(f'Data directory "{args.data_dir}" does not exist.')
        return

    # Execute the pipeline
    try:
        execute_pipeline(args.data_dir)
    except (FileNotFoundError, ValueError) as error:
        logger.critical(f'{str(error).removesuffix(".")}.')
    except Exception:
        logger.exception('An unexpected error occurred during pipeline execution.')


# Execute WUKONG Engine
if __name__ == '__main__':
    main()
