from pydantic import BaseModel, Field

from .chunking import ChunkingConfigSchema
from .export import ExportConfigSchema
from .llm import LLMConfigSchema
from .pipeline import PipelineConfigSchema


class ApplicationConfigSchema(BaseModel):
    """Application configuration schema."""

    pipeline: PipelineConfigSchema = Field(default_factory=PipelineConfigSchema)
    llm: LLMConfigSchema = Field(default_factory=LLMConfigSchema)
    chunking: ChunkingConfigSchema = Field(default_factory=ChunkingConfigSchema)
    export: ExportConfigSchema = Field(default_factory=ExportConfigSchema)
