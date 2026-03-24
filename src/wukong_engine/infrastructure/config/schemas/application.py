from pydantic import BaseModel

from .llm import LLMConfigSchema
from .pipeline import PipelineConfigSchema


class ApplicationConfigSchema(BaseModel):
    """Application configuration schema."""

    pipeline: PipelineConfigSchema
    llm: LLMConfigSchema
