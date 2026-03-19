from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.extraction.model.values import Language


class LLMSchema(BaseModel):
    """Schema-level representation of LLM parameters.

    Note: If context is None, the LLM should be prompted with no additional context.
    """

    persona: StrictStr = 'An AI expert specialized in knowledge graph extraction'
    document_context: StrictStr | None = None


class LanguageSchema(BaseModel):
    """Schema-level representation of language parameters."""

    input: Language = Language.EN
    output: Language = Language.EN

    # Mapping of various string representations to Language members
    _LANGUAGE_ALIASES: ClassVar[dict[str, Language]] = {
        'en': Language.EN,
        'english': Language.EN,
        'es': Language.ES,
        'spanish': Language.ES,
    }

    @field_validator('input', 'output', mode='before')
    @classmethod
    def normalize_language(cls, value: Any) -> Any:
        """Normalize language strings to Language members."""
        if isinstance(value, str):
            return cls._LANGUAGE_ALIASES.get(value, value)
        return value


class ProjectionSchema(BaseModel):
    """Schema-level representation of projection parameters.

    Note: None means that all entity/relationship types are enabled for extraction, while an empty list means that none are enabled.
    """

    enabled_entities: list[StrictStr] | None = None
    enabled_relationships: list[StrictStr] | None = None


class ExtractionConfigSchema(BaseModel):
    """Schema-level representation of extraction parameters."""

    llm: LLMSchema = Field(default_factory=LLMSchema)
    language: LanguageSchema = Field(default_factory=LanguageSchema)
    projection: ProjectionSchema = Field(default_factory=ProjectionSchema)
