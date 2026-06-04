import json
from dataclasses import dataclass

from wukong_engine.core.extraction.model.values import Language

from .values import EntityTypeName, RelationshipTypeName


@dataclass(frozen=True)
class ExtractionConfig:
    """The parameter configuration for the extraction process."""

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
