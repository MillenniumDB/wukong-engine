"""The main entry point for executing the WUKONG CLI.

This module is executed as a script and handles:
    - Parsing command-line arguments
    - Initializing the engine
    - Running the engine pipeline

Example:
    wukong run workspaces/example data/example --config config/default.toml -v
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from wukong_engine.app.shared.exceptions import ApplicationError
from wukong_engine.app.workspace import Workspace, WorkspaceValidator
from wukong_engine.bootstrap.cli import build_application

# Logging
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Parse command line arguments for the WUKONG CLI.

    Returns:
        A configured ArgumentParser instance.
    """
    # Main parser
    parser = argparse.ArgumentParser(
        prog='wukong',
        description='Engine for constructing knowledge graphs from unstructured documents, using the power of LLMs.',
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Run command
    run_parser = subparsers.add_parser(
        'run',
        help='Execute the WUKONG Engine pipeline over a workspace and data directory',
    )
    run_parser.add_argument(
        'workspace_dir',
        type=Path,
        help='Path to the workspace directory (e.g. workspaces/example)',
    )
    run_parser.add_argument(
        'data_dir',
        type=Path,
        help='Path to the data directory (e.g. data/example)',
    )
    run_parser.add_argument(
        '--config',
        type=Path,
        default=Path('./config/default.toml'),
        help='Path to the engine configuration file (e.g. config/default.toml)',
        metavar='CONFIG_FILE',
    )
    run_parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
        help='Select output verbosity (default: only show warning/error logs, -v: add info logs, -vv: add debug logs)',
    )
    run_parser.add_argument(
        '--reset',
        action='store_true',
        help='Clear all data at the start of each active pipeline step',
    )
    run_parser.set_defaults(func=handle_run)

    # Reset command
    reset_parser = subparsers.add_parser(
        'reset',
        help='Reset stored state for a workspace',
    )
    scope_group = reset_parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument(
        '--all',
        action='store_true',
        help='Reset everything',
    )
    scope_group.add_argument(
        '--entities',
        action='store_true',
        help='Reset extracted entities and relationships (keep documents)',
    )
    scope_group.add_argument(
        '--relationships',
        action='store_true',
        help='Reset extracted relationships (keep documents and entities)',
    )
    reset_parser.set_defaults(func=handle_reset)

    return parser


def handle_run(args: argparse.Namespace) -> None:
    """Run command execution.

    Args:
        args: Parsed command-line arguments.
    """
    try:
        print('Running WUKONG engine pipeline...')

        # Initialize workspace and validate along with data directory
        workspace = Workspace(root=args.workspace_dir)
        WorkspaceValidator().validate(workspace=workspace)
        if not args.data_dir.exists() or not args.data_dir.is_dir():
            logger.error(f'Data directory "{args.data_dir}" does not exist or is not a directory')
            logger.critical('Application Error: InvalidDataDirectoryError')
            sys.exit(1)

        # Build and run the pipeline
        app = build_application(workspace=workspace, config_path=args.config, verbosity=args.verbose)
        asyncio.run(
            app.graph_construction.execute(workspace=workspace, data_uri=args.data_dir, should_reset=args.reset),
        )
        print('WUKONG engine pipeline execution completed!')

    # Handle exceptions and exit
    except KeyboardInterrupt:
        logger.info('Program interrupted by user. Exiting.')
        sys.exit(130)  # SIGINT exit code
    except ApplicationError as exc:
        logger.critical(f'Application Error: {type(exc).__name__}')
        sys.exit(1)
    except Exception:
        logger.exception('Unhandled Exception')
        logger.critical('Unhandled Exception occurred during pipeline execution')
        sys.exit(1)


# TODO: New command for 'wukong reset <workspace>' that resets everything
def handle_reset(args: argparse.Namespace) -> None:
    """Reset command execution.

    Args:
        args: Parsed command-line arguments.
    """
    # reset_state(workspace=args.workspace)


def main() -> None:
    """Run the WUKONG CLI."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


# Execute the WUKONG engine CLI
if __name__ == '__main__':
    main()
