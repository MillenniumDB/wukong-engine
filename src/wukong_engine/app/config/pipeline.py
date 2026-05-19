"""Pipeline configuration model."""

from dataclasses import dataclass
from typing import ClassVar

from wukong_engine.core.pipeline.model.values import PipelineStep


@dataclass(frozen=True)
class PipelineConfig:
    """Pipeline configuration."""

    ingest_documents: bool = True
    extract_entities: bool = True
    extract_relationships: bool = True
    export_graph: bool = True

    # Mapping from pipeline steps to configuration fields
    _STEP_TO_FIELD: ClassVar[dict[PipelineStep, str]] = {
        PipelineStep.INGEST_DOCUMENTS: 'ingest_documents',
        PipelineStep.EXTRACT_ENTITIES: 'extract_entities',
        PipelineStep.EXTRACT_RELATIONSHIPS: 'extract_relationships',
        PipelineStep.EXPORT_GRAPH: 'export_graph',
    }

    def __str__(self) -> str:
        """User-friendly string representation of the pipeline configuration."""
        steps_str = ' → '.join(step.name for step in self.steps)
        return f'Steps: {steps_str}'

    @property
    def steps(self) -> tuple[PipelineStep, ...]:
        """Ordered active steps present in the configuration."""
        return tuple(step for step in PipelineStep if getattr(self, self._STEP_TO_FIELD[step]))

    def is_active(self, step: PipelineStep) -> bool:
        """Whether a pipeline step is active in this configuration."""
        return step in self.steps
