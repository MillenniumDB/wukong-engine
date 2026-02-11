from dataclasses import dataclass

from .values import EntityTypeName, Language, RelationshipTypeName


@dataclass(frozen=True)
class ExtractionConfig:
    """The parameter configuration for the extraction process."""

    llm_persona: str
    document_context: str | None
    input_language: Language
    output_language: Language
    entity_projection: frozenset[EntityTypeName] | None
    relationship_projection: frozenset[RelationshipTypeName] | None
