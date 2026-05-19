"""Schema-to-app mapping for application configuration."""

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.config.export import ExportConfig
from wukong_engine.app.config.llm import LLM, LLMConfig
from wukong_engine.app.config.pipeline import PipelineConfig

from .schemas import (
    ApplicationConfigSchema,
    ChunkingConfigSchema,
    ExportConfigSchema,
    LLMConfigSchema,
    PipelineConfigSchema,
)


class ApplicationConfigMapper:
    """Mapper from configuration schemas to application configuration models."""

    def map_configuration(self, schema: ApplicationConfigSchema) -> ApplicationConfig:
        """Map application configuration schema to application configuration model."""
        return ApplicationConfig(
            pipeline=self._map_pipeline(schema.pipeline),
            llm=self._map_llm(schema.llm),
            chunking=self._map_chunking(schema.chunking),
            export=self._map_export(schema.export),
        )

    def _map_pipeline(self, schema: PipelineConfigSchema) -> PipelineConfig:
        """Map pipeline configuration schema to pipeline configuration model."""
        return PipelineConfig(**schema.model_dump(exclude_none=True))

    def _map_llm(self, schema: LLMConfigSchema) -> LLMConfig:
        """Map llm configuration schema to llm configuration model."""
        default_config = LLMConfig()
        return LLMConfig(
            model=LLM(name=schema.model) if schema.model is not None else default_config.model,
            strict_support=schema.strict_support
            if schema.strict_support is not None
            else default_config.strict_support,
        )

    def _map_chunking(self, schema: ChunkingConfigSchema) -> ChunkingConfig:
        """Map chunking configuration schema to chunking configuration model."""
        return ChunkingConfig(**schema.model_dump(exclude_none=True))

    def _map_export(self, schema: ExportConfigSchema) -> ExportConfig:
        """Map export configuration schema to export configuration model."""
        return ExportConfig()
