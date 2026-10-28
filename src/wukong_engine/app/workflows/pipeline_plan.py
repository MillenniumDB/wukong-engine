"""Plan of what a run of the knowledge construction pipeline does, worked out before anything runs."""

from dataclasses import dataclass
from enum import Enum

from wukong_engine.core.pipeline.model.values import InputSnapshot, PipelineStep

# First step consuming each input snapshot: it is taken when that step runs, and kept until that step is reset
SNAPSHOT_STEPS: dict[InputSnapshot, PipelineStep] = {
    InputSnapshot.DOCUMENT_REGISTRY: PipelineStep.INGEST_DOCUMENTS,
    InputSnapshot.KNOWLEDGE_MODEL: PipelineStep.EXTRACT_ENTITIES,
}

# Name of the chunking settings in plans and warnings, which are snapshotted along with the document registry
CHUNKING_INPUT_NAME = '[chunking] settings'


class StepAction(Enum):
    """What a run does with a pipeline step.

    Attributes:
        RUN: The step is enabled and not completed, so it runs, resuming any work left by earlier runs.
        RESET_AND_RUN: The step is enabled and reset by the run, so it runs from scratch.
        SKIP: The step is enabled but already completed, so it is skipped.
        RESET: The step is disabled, but the reset of an earlier step clears its results.
        KEEP: The step is disabled, and its completed results are kept.
        NOT_RUN: The step is disabled and has no completed results.
    """

    RUN = 'RUN'
    RESET_AND_RUN = 'RESET_AND_RUN'
    SKIP = 'SKIP'
    RESET = 'RESET'
    KEEP = 'KEEP'
    NOT_RUN = 'NOT_RUN'

    @property
    def runs(self) -> bool:
        """Whether the step runs."""
        return self in {StepAction.RUN, StepAction.RESET_AND_RUN}

    @property
    def description(self) -> str:
        """User-friendly description of the action."""
        return STEP_ACTION_DESCRIPTIONS[self]


STEP_ACTION_DESCRIPTIONS: dict[StepAction, str] = {
    StepAction.RUN: 'Run',
    StepAction.RESET_AND_RUN: 'Reset, then run from scratch',
    StepAction.SKIP: 'Skip (already completed)',
    StepAction.RESET: 'Reset (disabled, but an earlier step is reset)',
    StepAction.KEEP: 'Keep completed results (disabled)',
    StepAction.NOT_RUN: 'Not run (disabled)',
}


class InputSource(Enum):
    """Where a run reads one of its inputs from.

    Attributes:
        SNAPSHOT: The snapshot kept for the workspace, which matches the current input.
        OUTDATED_SNAPSHOT: The snapshot kept for the workspace, although the current input changed since it was taken.
        NEW_SNAPSHOT: The current input, snapshotted by the run since the step that takes its snapshot runs.
        CURRENT: The current input, not snapshotted since the step that would take its snapshot doesn't run.
    """

    SNAPSHOT = 'SNAPSHOT'
    OUTDATED_SNAPSHOT = 'OUTDATED_SNAPSHOT'
    NEW_SNAPSHOT = 'NEW_SNAPSHOT'
    CURRENT = 'CURRENT'

    @property
    def uses_snapshot(self) -> bool:
        """Whether the input is read from a snapshot taken by an earlier run."""
        return self in {InputSource.SNAPSHOT, InputSource.OUTDATED_SNAPSHOT}


@dataclass(frozen=True, slots=True)
class InputPlan:
    """Where a run reads one of its inputs from.

    Attributes:
        name: User-facing name of the input (e.g. ``knowledge_model.json``).
        step: Step that snapshots the input when it first runs.
        source: Where the input is read from.
    """

    name: str
    step: PipelineStep
    source: InputSource

    def __str__(self) -> str:
        """User-friendly string representation of the input plan."""
        match self.source:
            case InputSource.SNAPSHOT:
                return f'{self.name}: Snapshot taken by {self.step.value}'
            case InputSource.OUTDATED_SNAPSHOT:
                return (
                    f'{self.name}: Snapshot taken by {self.step.value}, ignoring changes made since '
                    f'(reset {self.step.value} to apply them)'
                )
            case InputSource.NEW_SNAPSHOT:
                return f'{self.name}: Current version, snapshotted by {self.step.value}'
            case InputSource.CURRENT:
                return f'{self.name}: Current version'


@dataclass(frozen=True, slots=True)
class PipelinePlan:
    """What a run of the pipeline does with each step and where it reads its inputs from.

    A run stops at the first step it runs that doesn't complete (e.g. while batches are pending), leaving the steps
    after it for later runs.

    Attributes:
        steps: Action taken on each pipeline step, in pipeline order.
        inputs: Where each input is read from.
    """

    steps: dict[PipelineStep, StepAction]
    inputs: tuple[InputPlan, ...]

    @property
    def runs_any_step(self) -> bool:
        """Whether the run runs at least one step."""
        return any(action.runs for action in self.steps.values())

    def __str__(self) -> str:
        """User-friendly string representation of the pipeline plan."""
        width = max(len(step.value) for step in self.steps)
        lines = []
        lines.append('=' * 80)
        lines.append(' PLAN')
        lines.append('=' * 80)

        lines.append('\n[STEPS]\n')
        lines.extend(f'  {step.value:<{width}}  {action.description}' for step, action in self.steps.items())

        lines.append('\n[INPUTS]\n')
        lines.extend(f'  {input_plan}' for input_plan in self.inputs)

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)
