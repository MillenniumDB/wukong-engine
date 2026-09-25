"""Pydantic schemas for the extraction config section of a knowledge model definition."""

from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.extraction.model.values import Language


class LLMSchema(BaseModel):
    """Schema-level representation of LLM parameters.

    Attributes:
        domain: Description of the domain of the source documents, given to the LLM as context.
        language: Language of the source documents, or None if unspecified. Accepts codes or names (e.g. "en",
            "spanish"), case-insensitively.
    """

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
        """Normalize language strings to Language members.

        Args:
            value: Raw input for the ``language`` field.

        Returns:
            The matching Language member if ``value`` is a known alias, otherwise ``value`` unchanged for regular
            validation.
        """
        if isinstance(value, str):
            return cls._LANGUAGE_ALIASES.get(value.strip().lower(), value)
        return value


class ProjectionSchema(BaseModel):
    """Schema-level representation of projection parameters.

    Note: None means that all entity/relationship types are enabled for extraction, while an empty list means that none are enabled.

    Attributes:
        enabled_entities: Names of the entity types enabled for extraction, or None to enable all.
        enabled_relationships: Names of the relationship types enabled for extraction, or None to enable all.
    """

    enabled_entities: list[StrictStr] | None = None
    enabled_relationships: list[StrictStr] | None = None


class ExtractionConfigSchema(BaseModel):
    """Schema-level representation of extraction parameters.

    Attributes:
        llm: LLM parameters.
        projection: Which entity and relationship types are enabled for extraction.
    """

    llm: LLMSchema = Field(default_factory=LLMSchema)
    projection: ProjectionSchema = Field(default_factory=ProjectionSchema)
