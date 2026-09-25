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
        """Map application configuration schema to application configuration model.

        Settings left unset in the schema fall back to the defaults of the configuration models.

        Args:
            schema: Validated application configuration schema.

        Returns:
            The application configuration.

        Raises:
            ValueError: If any mapped configuration section fails validation.
        """
        return ApplicationConfig(
            pipeline=self._map_pipeline(schema.pipeline),
            llm=self._map_llm(schema.llm),
            chunking=self._map_chunking(schema.chunking),
            export=self._map_export(schema.export),
        )

    def _map_pipeline(self, schema: PipelineConfigSchema) -> PipelineConfig:
        """Map pipeline configuration schema to pipeline configuration model.

        Args:
            schema: Pipeline configuration schema.

        Returns:
            The pipeline configuration, using the model defaults for unset steps.
        """
        return PipelineConfig(**schema.model_dump(exclude_none=True))

    def _map_llm(self, schema: LLMConfigSchema) -> LLMConfig:
        """Map LLM configuration schema to LLM configuration model.

        Args:
            schema: LLM configuration schema. A non-empty ``model`` name is wrapped into an ``LLM``.

        Returns:
            The LLM configuration, using the model defaults for unset fields.
        """
        kwargs = schema.model_dump(exclude_none=True)
        if kwargs.get('model'):
            kwargs['model'] = LLM(name=kwargs['model'])
        return LLMConfig(**kwargs)

    def _map_chunking(self, schema: ChunkingConfigSchema) -> ChunkingConfig:
        """Map chunking configuration schema to chunking configuration model.

        Args:
            schema: Chunking configuration schema.

        Returns:
            The chunking configuration, using the model defaults (or derived values) for unset fields.
        """
        return ChunkingConfig(**schema.model_dump(exclude_none=True))

    def _map_export(self, schema: ExportConfigSchema) -> ExportConfig:
        """Map export configuration schema to export configuration model.

        Args:
            schema: Export configuration schema.

        Returns:
            The export configuration, using the model default for an unset format.
        """
        return ExportConfig(**schema.model_dump(exclude_none=True))
