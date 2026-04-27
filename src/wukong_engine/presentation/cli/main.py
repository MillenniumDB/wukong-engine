"""The main entry point for executing the WUKONG CLI.

This module is executed as a script and handles:
    - Parsing command-line arguments
    - Initializing the engine
    - Running the engine pipeline

Example:
    wukong workspaces/example --config config/default.toml
"""

import argparse
import logging
import sys
from pathlib import Path

from wukong_engine.app.workspace import Workspace, WorkspaceValidator
from wukong_engine.bootstrap.cli import build_application

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
        help='Execute the WUKONG Engine pipeline over a workspace',
    )
    run_parser.add_argument(
        'workspace',
        type=Path,
        help='Path to the workspace directory (e.g. workspaces/example)',
    )
    run_parser.add_argument(
        '--config',
        type=Path,
        default=Path('./config/default.toml'),
        help='Path to the engine configuration file (e.g. config/default.toml)',
        metavar='CONFIG_FILE',
    )
    run_parser.add_argument(
        '--incremental',
        action='store_true',
        help='Reuse existing state instead of resetting active steps',
    )
    run_parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
        help='Select output verbosity (default: only show warning/error logs, -v: add info logs, -vv: add debug logs)',
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
        print('Starting WUKONG...')
        workspace = Workspace(root=args.workspace)
        WorkspaceValidator().validate(workspace=workspace)
        app = build_application(workspace=workspace, config_path=args.config, verbosity=args.verbose)
        app.graph_construction.execute(workspace=workspace, should_reset=not args.incremental)
        print('WUKONG pipeline execution completed!')
    except (FileNotFoundError, ValueError, TypeError) as error:
        logger.exception('Failed to process input.')
        print_error(str(error))
        sys.exit(1)
    except Exception:
        logger.exception('Unhandled exception.')
        print('Error: An unexpected error occurred.', file=sys.stderr)
        sys.exit(1)


# TODO: New command for 'wukong reset <workspace>' with flags for --all, --entities, --relationships
def handle_reset(args: argparse.Namespace) -> None:
    """Reset command execution.

    Args:
        args: Parsed command-line arguments.
    """
    if args.all:
        scope = 'all'
    elif args.entities:
        scope = 'entities'
    else:
        scope = 'relationships'
    # reset_state(scope=scope, confirm=args.yes)


def main() -> None:
    """Run the WUKONG CLI."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


# Execute the WUKONG engine CLI
if __name__ == '__main__':
    main()
