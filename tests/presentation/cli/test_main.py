"""Tests for the commands of the WUKONG CLI."""

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any

import pytest

from wukong_engine.app.config.pipeline import PipelineConfig
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.core.pipeline.model.values import PipelineStep

# The CLI package exports the main function under the name of its module, so the module is looked up by its path
cli = importlib.import_module('wukong_engine.presentation.cli.main')

# Outcomes of a run of the fake pipeline that doesn't fail
DONE = True
UNFINISHED = False


class FakePipeline:
    """Pipeline (and reset) recording its calls, whose runs end with the given outcomes in turn: done, unfinished or an error."""

    def __init__(self, *outcomes: bool | Exception) -> None:
        """Initialize the pipeline with the outcome of each run."""
        self.outcomes = list(outcomes)
        self.calls: list[str] = []

    def plan(self, *_: Any, should_reset: bool) -> None:
        """Record the plan."""
        self.calls.append(f'plan reset={should_reset}')

    async def reset(self, from_step: PipelineStep) -> None:
        """Record the reset."""
        self.calls.append(f'reset from {from_step.value}')

    async def execute(self, *, should_reset: bool, **_: Any) -> bool:
        """Record the run and end it with its outcome."""
        self.calls.append(f'run reset={should_reset}')
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _run_until_done(pipeline: FakePipeline, *, should_reset: bool = False) -> None:
    """Run the pipeline until done with entity extraction as its first enabled step and no wait between runs."""
    app = SimpleNamespace(
        config=SimpleNamespace(
            llm=SimpleNamespace(execution_mode=ExecutionMode.BATCH),
            pipeline=PipelineConfig(ingest_documents=False),
        ),
        knowledge_construction=pipeline,
        reset_pipeline=SimpleNamespace(execute=pipeline.reset),
    )
    asyncio.run(cli._run_until_done(app, SimpleNamespace(), 'data', should_reset=should_reset))


@pytest.fixture(autouse=True)
def no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the wait between runs."""
    monkeypatch.setattr(cli, 'UNTIL_DONE_INTERVALS', dict.fromkeys(ExecutionMode, 0))


def test_until_done_resets_once_before_the_first_run(capsys: pytest.CaptureFixture[str]) -> None:
    """Reset only once, after checking the plan, so that the runs after a failed first one never reset again."""
    pipeline = FakePipeline(UNFINISHED, UNFINISHED, DONE)

    _run_until_done(pipeline, should_reset=True)

    assert pipeline.calls == [
        'plan reset=True',
        'reset from EXTRACT_ENTITIES',
        'run reset=False',
        'run reset=False',
        'run reset=False',
    ]
    assert 'Run 2 left steps unfinished' in capsys.readouterr().out


def test_until_done_gives_up_after_too_many_failed_runs_in_a_row() -> None:
    """Retry failed runs, counting only consecutive failures, until too many fail in a row."""
    pipeline = FakePipeline(RuntimeError(), UNFINISHED, RuntimeError(), RuntimeError(), RuntimeError('last'))

    with pytest.raises(RuntimeError, match='last'):
        _run_until_done(pipeline)

    assert len(pipeline.calls) == 5


def test_until_done_stops_at_errors_caused_by_the_inputs() -> None:
    """Don't retry a run that failed because of its inputs, since every later run would fail the same way."""
    pipeline = FakePipeline(ModelIngestionError())

    with pytest.raises(ModelIngestionError):
        _run_until_done(pipeline)

    assert pipeline.calls == ['run reset=False']


@pytest.mark.parametrize(
    ('answer', 'confirmed'),
    [('y', True), ('Y', True), (' Yes ', True), ('YES', True), ('', False), ('n', False), ('yep', False)],
)
def test_only_affirmative_answers_confirm(monkeypatch: pytest.MonkeyPatch, answer: str, *, confirmed: bool) -> None:
    """Accept y and yes in any case, defaulting to no for anything else."""
    monkeypatch.setattr('builtins.input', lambda _: answer)

    assert cli._confirm('Continue?') is confirmed


def test_a_prompt_without_input_is_not_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse when no answer can be read, as when running without an interactive terminal."""

    def closed_input(_: str) -> str:
        raise EOFError

    monkeypatch.setattr('builtins.input', closed_input)

    assert not cli._confirm('Continue?')
