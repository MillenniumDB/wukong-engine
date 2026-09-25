"""Schema for the application configuration file."""

from pydantic import BaseModel, Field

from .chunking import ChunkingConfigSchema
from .export import ExportConfigSchema
from .llm import LLMConfigSchema
from .pipeline import PipelineConfigSchema


class ApplicationConfigSchema(BaseModel):
    """Application configuration schema.

    Attributes:
        pipeline: Pipeline step toggles (``[pipeline]`` table).
        llm: LLM settings (``[llm]`` table).
        chunking: Document chunking settings (``[chunking]`` table).
        export: Knowledge export settings (``[export]`` table).
    """

    pipeline: PipelineConfigSchema = Field(default_factory=PipelineConfigSchema)
    llm: LLMConfigSchema = Field(default_factory=LLMConfigSchema)
    chunking: ChunkingConfigSchema = Field(default_factory=ChunkingConfigSchema)
    export: ExportConfigSchema = Field(default_factory=ExportConfigSchema)
