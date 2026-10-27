"""The main entry point for executing the WUKONG CLI.

This module is executed as a script and handles:
    - Parsing command-line arguments
    - Initializing the engine
    - Running, planning, resetting or reporting the status of the engine pipeline

Example:
    wukong run workspaces/example data/example --config config/default.toml -v
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.app.shared.exceptions import ApplicationError, PipelineExecutionError
from wukong_engine.app.workspace import Workspace, WorkspaceValidator
from wukong_engine.bootstrap.cli import CLIApplication, build_application, build_pipeline_status
from wukong_engine.core.pipeline.model.values import PipelineStep

# Logging
logger = logging.getLogger(__name__)

# Pipeline steps as named in the command line
STEP_NAMES: dict[str, PipelineStep] = {step.value.lower(): step for step in PipelineStep}

# Answers to a confirmation prompt that confirm it, compared in lowercase
AFFIRMATIVE_ANSWERS = frozenset({'y', 'yes'})

# Seconds a run with --until-done waits between passes: batches take minutes to hours to end at the provider
UNTIL_DONE_INTERVALS: dict[ExecutionMode, int] = {
    ExecutionMode.REALTIME: 60,
    ExecutionMode.BATCH: 300,
}

# Consecutive failed passes after which a run with --until-done gives up
MAX_CONSECUTIVE_FAILURES = 3

# Errors caused by the inputs, which every later pass would hit again
NON_RETRYABLE_ERRORS: tuple[type[ApplicationError], ...] = (ModelIngestionError, PipelineExecutionError)


def _add_workspace_argument(parser: argparse.ArgumentParser) -> None:
    """Add the workspace directory argument to a command parser.

    Args:
        parser: Parser of the command.
    """
    parser.add_argument(
        'workspace_dir',
        type=Path,
        help='Path to the workspace directory (e.g. workspaces/example)',
    )


def _add_data_argument(parser: argparse.ArgumentParser) -> None:
    """Add the data directory argument to a command parser.

    Args:
        parser: Parser of the command.
    """
    parser.add_argument(
        'data_dir',
        type=Path,
        help='Path to the data directory (e.g. data/example)',
    )


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the configuration file and verbosity options to a command parser.

    Args:
        parser: Parser of the command.
    """
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
        help='Select output verbosity (default: only show warning/error logs, -v: add info logs, -vv: add debug logs)',
    )


def _add_reset_argument(parser: argparse.ArgumentParser) -> None:
    """Add the reset flag to a command parser.

    Args:
        parser: Parser of the command.
    """
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Clear all data at the start of each active pipeline step and the steps depending on it',
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for the WUKONG CLI.

    Returns:
        A configured ArgumentParser instance, with the ``run``, ``plan``, ``status`` and ``reset`` subcommands bound to
        their handlers.
    """
    # Main parser
    parser = argparse.ArgumentParser(
        prog='wukong',
        description='Engine for extracting structured knowledge from unstructured documents using the power of LLMs, exportable to graph and other formats.',
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Run command
    run_parser = subparsers.add_parser(
        'run',
        help='Execute the WUKONG Engine pipeline over a workspace and data directory',
        allow_abbrev=False,
    )
    _add_workspace_argument(run_parser)
    _add_data_argument(run_parser)
    _add_config_arguments(run_parser)
    _add_reset_argument(run_parser)
    run_parser.add_argument(
        '--until-done',
        action='store_true',
        help='Keep running the pipeline, waiting between runs, until every enabled step is completed',
    )
    run_parser.set_defaults(func=handle_run)

    # Plan command
    plan_parser = subparsers.add_parser(
        'plan',
        help='Show the configuration and what the run command would do with the same arguments, without running it',
        allow_abbrev=False,
    )
    _add_workspace_argument(plan_parser)
    _add_data_argument(plan_parser)
    _add_config_arguments(plan_parser)
    _add_reset_argument(plan_parser)
    plan_parser.set_defaults(func=handle_plan)

    # Status command
    status_parser = subparsers.add_parser(
        'status',
        help='Show the progress of each pipeline step in a workspace',
        allow_abbrev=False,
    )
    _add_workspace_argument(status_parser)
    status_parser.set_defaults(func=handle_status)

    # Reset command
    reset_parser = subparsers.add_parser(
        'reset',
        help='Clear the stored results of a workspace, entirely or from a pipeline step onwards, without running it',
        allow_abbrev=False,
    )
    _add_workspace_argument(reset_parser)
    reset_parser.add_argument(
        '--from',
        dest='from_step',
        type=str.lower,
        choices=STEP_NAMES,
        default=PipelineStep.INGEST_DOCUMENTS.value.lower(),
        help='First step to reset, along with every step after it (default: the first step, resetting everything)',
        metavar='STEP',
    )
    _add_config_arguments(reset_parser)
    reset_parser.add_argument(
        '-y',
        '--yes',
        action='store_true',
        help='Reset without asking for confirmation',
    )
    reset_parser.set_defaults(func=handle_reset)

    return parser


def _load_workspace(workspace_dir: Path) -> Workspace:
    """Load and validate a workspace.

    Args:
        workspace_dir: Root directory of the workspace.

    Returns:
        The validated workspace.

    Raises:
        InvalidWorkspaceError: If the workspace directory or its input files are missing.
    """
    workspace = Workspace(root=workspace_dir)
    WorkspaceValidator().validate(workspace=workspace)
    return workspace


def _validate_data_dir(data_dir: Path) -> None:
    """Exit the process with status 1 if the data directory doesn't exist.

    Args:
        data_dir: Data directory to check.
    """
    if not data_dir.is_dir():
        logger.error(f'Data directory "{data_dir}" does not exist or is not a directory')
        logger.critical('Application Error: InvalidDataDirectoryError')
        sys.exit(1)


def _confirm(question: str) -> bool:
    """Ask the user a yes/no question, defaulting to no.

    Args:
        question: Question to ask.

    Returns:
        True if the user answered affirmatively, False otherwise or if no answer could be read.
    """
    try:
        answer = input(f'{question} [y/N] ')
    except EOFError:
        print('\nNo answer could be read; pass --yes to skip the confirmation.')
        return False
    return answer.strip().lower() in AFFIRMATIVE_ANSWERS


async def _run_until_done(app: CLIApplication, workspace: Workspace, data_uri: str, *, should_reset: bool) -> None:
    """Run the pipeline again and again, waiting between passes, until every enabled step is completed.

    A pass that fails is retried, unless the failure comes from the inputs, until it fails too many times in a row.

    Args:
        app: Application whose pipeline is run.
        workspace: Workspace the pipeline runs over.
        data_uri: Data location the documents are ingested from.
        should_reset: Whether to reset the enabled steps and the steps depending on them before the first pass.

    Raises:
        ApplicationError: If a pass fails because of the inputs, or too many passes fail in a row.
    """
    pipeline = app.knowledge_construction
    interval = UNTIL_DONE_INTERVALS[app.config.llm.execution_mode]

    # Resetting within the first pass would leave it unknown whether a later pass must still reset, if the first one
    # failed, so the reset is done on its own, once the plan is checked. Resetting from the first enabled step resets
    # exactly the steps a run with --reset does, since every step after it depends on it
    if should_reset and app.config.pipeline.steps:
        pipeline.plan(workspace, data_uri, should_reset=True)
        await pipeline.reset(from_step=app.config.pipeline.steps[0])

    failures = 0
    attempt = 0
    while True:
        attempt += 1
        try:
            if await pipeline.execute(workspace=workspace, data_uri=data_uri, should_reset=False):
                return
            failures = 0
            print(f'Run {attempt} left steps unfinished. Running again in {interval} seconds (Ctrl+C to stop)...')
        except NON_RETRYABLE_ERRORS:
            raise
        except Exception:
            failures += 1
            logger.exception(f'Run {attempt} failed')
            if failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(f'Giving up after {failures} failed runs in a row')
                raise
            print(
                f'Run {attempt} failed ({failures}/{MAX_CONSECUTIVE_FAILURES} in a row). '
                f'Retrying in {interval} seconds (Ctrl+C to stop)...',
            )
        await asyncio.sleep(interval)


def handle_run(args: argparse.Namespace) -> None:
    """Execute the run command.

    Validates the workspace and data directory, then runs the knowledge construction pipeline, once or until it is
    completed.

    Args:
        args: Parsed command-line arguments.
    """
    print('Running WUKONG engine pipeline...')
    workspace = _load_workspace(args.workspace_dir)
    _validate_data_dir(args.data_dir)
    data_uri = str(args.data_dir)

    app = build_application(workspace=workspace, config_path=args.config, verbosity=args.verbose)
    if args.until_done:
        asyncio.run(_run_until_done(app, workspace, data_uri, should_reset=args.reset))
    elif not asyncio.run(
        app.knowledge_construction.execute(workspace=workspace, data_uri=data_uri, should_reset=args.reset),
    ):
        print('WUKONG engine pipeline stopped with steps left unfinished. Run it again, or use --until-done.')
        return
    print('WUKONG engine pipeline execution completed!')


def handle_plan(args: argparse.Namespace) -> None:
    """Execute the plan command.

    Shows the configuration, then what the run command would do with the same arguments, without running, resetting or
    snapshotting anything.

    Args:
        args: Parsed command-line arguments.
    """
    workspace = _load_workspace(args.workspace_dir)
    _validate_data_dir(args.data_dir)

    app = build_application(workspace=workspace, config_path=args.config, verbosity=args.verbose)
    print(app.config)
    plan = app.knowledge_construction.plan(workspace=workspace, data_uri=str(args.data_dir), should_reset=args.reset)
    print(plan)
    if not plan.runs_any_step and app.config.pipeline.steps:
        print(
            'No step would run: every enabled step is already completed. Pass --reset to run them again, or clear '
            'the workspace with the reset command.',
        )
    elif not plan.runs_any_step:
        print('No step would run: enable the steps to run in the [pipeline] section of the configuration.')


def handle_status(args: argparse.Namespace) -> None:
    """Execute the status command.

    Shows the progress of each pipeline step and the snapshots of the inputs, without needing a configuration.

    Args:
        args: Parsed command-line arguments.
    """
    workspace = _load_workspace(args.workspace_dir)
    if not workspace.paths.staging_db.exists():
        print(f'No pipeline step has run in workspace "{workspace.paths.root}" yet.')
        return
    print(build_pipeline_status(workspace).execute(workspace))


def handle_reset(args: argparse.Namespace) -> None:
    """Execute the reset command.

    Asks for confirmation unless ``--yes`` is given, then resets the chosen step and every step after it. Exits the
    process with status 1 if the reset is not confirmed, so that commands chained after it don't run.

    Args:
        args: Parsed command-line arguments.
    """
    workspace = _load_workspace(args.workspace_dir)
    if not workspace.paths.staging_db.exists():
        print(f'Nothing to reset: no pipeline step has run in workspace "{workspace.paths.root}" yet.')
        return

    from_step = STEP_NAMES[args.from_step]
    steps = [step for step in PipelineStep if step in {from_step, *from_step.is_required_by}]
    if not args.yes:
        print(f'This permanently clears the results of these steps in workspace "{workspace.paths.root}":')
        print('\n'.join(f'  - {step.value}' for step in steps))
        if {PipelineStep.EXTRACT_ENTITIES, PipelineStep.EXTRACT_RELATIONSHIPS} & set(steps):
            print('Batches of these steps still running at the provider are cancelled.')
        if not _confirm('Continue?'):
            print('Reset cancelled.')
            sys.exit(1)

    app = build_application(workspace=workspace, config_path=args.config, verbosity=args.verbose)
    asyncio.run(app.knowledge_construction.reset(from_step=from_step))
    print(f'Reset {", ".join(step.value for step in steps)}.')


def main() -> None:
    """Run the WUKONG CLI.

    Exits the process with status 1 on invalid input or errors, and 130 if interrupted by the user.
    """
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)

    # Handle exceptions and exit
    except KeyboardInterrupt:
        logger.info('Program interrupted by user. Exiting.')
        sys.exit(130)  # SIGINT exit code
    except ApplicationError as exc:
        logger.critical(f'Application Error: {type(exc).__name__}')
        sys.exit(1)
    except Exception:
        logger.exception('Unhandled Exception')
        logger.critical('Unhandled Exception occurred during command execution')
        sys.exit(1)


# Execute the WUKONG engine CLI
if __name__ == '__main__':
    main()
