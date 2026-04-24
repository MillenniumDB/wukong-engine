"""Schema-to-app mapping for application configuration."""

from typing import ClassVar

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.config.llm import LLM, LLMConfig
from wukong_engine.app.config.pipeline import PipelineConfig
from wukong_engine.core.pipeline.model.values import PipelineStep

from .schemas import ApplicationConfigSchema, LLMConfigSchema, PipelineConfigSchema


class ApplicationConfigMapper:
    """Mapper from configuration schemas to application configuration models."""

    _FIELD_TO_STEP: ClassVar[dict[str, PipelineStep]] = {
        'extract_entities': PipelineStep.EXTRACT_ENTITIES,
        'extract_relationships': PipelineStep.EXTRACT_RELATIONSHIPS,
        'export_graph': PipelineStep.EXPORT_GRAPH,
    }

    def map_configuration(self, schema: ApplicationConfigSchema) -> ApplicationConfig:
        """Map application configuration schema to application configuration model."""
        return ApplicationConfig(
            pipeline=self._map_pipeline(schema.pipeline),
            llm=self._map_llm(schema.llm),
        )

    def _map_pipeline(self, schema: PipelineConfigSchema) -> PipelineConfig:
        """Map pipeline configuration schema to pipeline configuration model."""
        enabled = {step for field, step in self._FIELD_TO_STEP.items() if getattr(schema, field)}
        return PipelineConfig(run_mode=schema.run_mode, steps=frozenset(enabled))

    def _map_llm(self, schema: LLMConfigSchema) -> LLMConfig:
        """Map llm configuration schema to llm configuration model."""
        return LLMConfig(
            model=LLM(name=schema.model),
            strict=schema.strict,
        )
