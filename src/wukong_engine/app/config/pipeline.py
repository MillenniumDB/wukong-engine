"""Pipeline configuration model."""

from dataclasses import dataclass

from wukong_engine.core.pipeline.model.values import PipelineStep


@dataclass(frozen=True)
class PipelineConfig:
    """Pipeline configuration."""

    steps: frozenset[PipelineStep]

    def __str__(self) -> str:
        """User-friendly string representation of the pipeline configuration."""
        steps_str = ' → '.join(step.name for step in self.active_steps)
        return f'Steps: {steps_str}'

    @property
    def active_steps(self) -> tuple[PipelineStep, ...]:
        """Ordered active steps present in the configuration."""
        return tuple(step for step in PipelineStep if step in self.steps)

    def is_active(self, step: PipelineStep) -> bool:
        """Whether a pipeline step is active in this configuration."""
        return step in self.steps
