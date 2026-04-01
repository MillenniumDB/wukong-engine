import json
from dataclasses import dataclass

from wukong_engine.core.extraction.model.values import Language

from .values import EntityTypeName, RelationshipTypeName


@dataclass(frozen=True)
class ExtractionConfig:
    """The parameter configuration for the extraction process."""

    llm_persona: str
    domain_context: str | None
    input_language: Language
    output_language: Language
    entity_projection: frozenset[EntityTypeName] | None
    relationship_projection: frozenset[RelationshipTypeName] | None

    def __str__(self) -> str:
        """User-friendly string representation of the extraction config."""
        lines = []
        lines.append(f'• LLM Persona: {self.llm_persona}')
        lines.append(f'Domain Context: {self.domain_context}')
        lines.append(f'Input Language: {self.input_language.value}')
        lines.append(f'Output Language: {self.output_language.value}')
        return '\n• '.join(lines)

    def __repr__(self) -> str:
        """JSON representation of the extraction config."""
        config = {
            'llm_persona': self.llm_persona,
            'domain_context': self.domain_context,
            'language': self.output_language.value,
        }
        return json.dumps(config)
