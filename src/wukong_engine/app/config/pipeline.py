"""Pipeline configuration model."""

from dataclasses import dataclass
from enum import Enum

from wukong_engine.core.pipeline.model.values import PipelineStep


class RunMode(Enum):
    """Run modes for the pipeline, controlling execution behavior and assumptions about the environment.

    Attributes:
        EXPERIMENTAL: The pipeline accepts any graph model and document collections, and clears data at the start of each run (meant for testing).
        PRODUCTION: The pipeline assumes a fixed graph model and document collections, and keeps data across runs (meant for full extraction).
    """

    EXPERIMENTAL = 'experimental'
    PRODUCTION = 'production'


# TODO: Move RunMode to run context
@dataclass(frozen=True)
class PipelineConfig:
    """Pipeline configuration."""

    run_mode: RunMode
    steps: frozenset[PipelineStep]

    def __str__(self) -> str:
        """User-friendly string representation of the pipeline configuration."""
        steps_str = ' → '.join(step.name for step in self.active_steps)
        return f'Mode: {self.run_mode.value}, Steps: {steps_str}'

    @property
    def active_steps(self) -> tuple[PipelineStep, ...]:
        """Ordered active steps present in the configuration."""
        return tuple(step for step in PipelineStep if step in self.steps)

    def is_active(self, step: PipelineStep) -> bool:
        """Whether a pipeline step is active in this configuration."""
        return step in self.steps
