from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.extraction.model.values import Language


class LLMSchema(BaseModel):
    """Schema-level representation of LLM parameters."""

    domain: StrictStr = 'General documents.'
    language: Language | None = None

    # Mapping of various string representations to Language members
    _LANGUAGE_ALIASES: ClassVar[dict[str, Language]] = {
        'en': Language.EN,
        'english': Language.EN,
        'es': Language.ES,
        'spanish': Language.ES,
    }

    @field_validator('language', mode='before')
    @classmethod
    def normalize_language(cls, value: Any) -> Any:
        """Normalize language strings to Language members."""
        if isinstance(value, str):
            return cls._LANGUAGE_ALIASES.get(value.strip().lower(), value)
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
    projection: ProjectionSchema = Field(default_factory=ProjectionSchema)
