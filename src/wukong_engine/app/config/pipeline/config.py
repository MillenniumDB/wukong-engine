from dataclasses import dataclass

from .step import PipelineStep


@dataclass(frozen=True)
class PipelineConfig:
    """Pipeline configuration."""

    steps: frozenset[PipelineStep]

    def __str__(self) -> str:
        """User-friendly string representation of the pipeline configuration."""
        steps_str = ' → '.join(step.name for step in PipelineStep if step in self.steps)
        return f'Steps: {steps_str}'
