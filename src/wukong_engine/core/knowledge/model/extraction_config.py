"""Extraction process configuration from the knowledge model."""

import json
from dataclasses import dataclass

from wukong_engine.core.extraction.model.values import Language

from .values import EntityTypeName, RelationshipTypeName


@dataclass(frozen=True, slots=True)
class ExtractionConfig:
    """The parameter configuration for the extraction process.

    Attributes:
        domain: Description of the domain of the source documents, given to the LLM as context.
        language: Language of the source documents, or None if unspecified.
        entity_projection: Entity types enabled for extraction, or None to enable all of them.
        relationship_projection: Relationship types enabled for extraction, or None to enable all of them.
    """

    domain: str
    language: Language | None
    entity_projection: frozenset[EntityTypeName] | None
    relationship_projection: frozenset[RelationshipTypeName] | None

    def __str__(self) -> str:
        """User-friendly string representation of the extraction config."""
        lines = []
        lines.append(f'• Domain: {self.domain}')
        if self.language is not None:
            lines.append(f'Language: {self.language.value}')
        return '\n• '.join(lines)

    def __repr__(self) -> str:
        """JSON representation of the extraction config."""
        config = {'domain': self.domain}
        return json.dumps(config)
