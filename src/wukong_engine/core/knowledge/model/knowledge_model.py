"""Provides a knowledge model interface for the engine.

Classes:
    KnowledgeModel: The knowledge model containing all entity types.
"""

import json
from dataclasses import dataclass
from types import MappingProxyType

from .endpoint import Endpoint
from .entity_type import EntityType
from .extraction_config import ExtractionConfig
from .relationship_type import RelationshipType
from .values import EntityTypeName, RelationshipTypeName


@dataclass(frozen=True)
class KnowledgeModel:
    """The knowledge model containing all entity types."""

    extraction_config: ExtractionConfig
    entity_types: MappingProxyType[EntityTypeName, EntityType]
    relationship_types: MappingProxyType[RelationshipTypeName, RelationshipType]

    def __str__(self) -> str:
        """User-friendly string representation of the knowledge model."""
        lines = []
        lines.append('=' * 80)
        lines.append(' KNOWLEDGE MODEL')
        lines.append('=' * 80)

        # Extraction Config
        lines.append('\n[EXTRACTION CONFIG]\n')
        lines.extend(f'  {line}' for line in str(self.extraction_config).split('\n'))

        # Entity Types
        lines.append(f'\n[ENTITY TYPES] ({len(self.active_entity_types)} total)')
        for entity_type in self.active_entity_types.values():
            lines.append('')
            lines.extend(f'  {line}' for line in str(entity_type).split('\n'))

        # Relationship Types
        lines.append(f'\n[RELATIONSHIP TYPES] ({len(self.active_relationship_types)} total)')
        for rel_type in self.active_relationship_types.values():
            lines.append('')
            lines.extend(f'  {line}' for line in str(rel_type).split('\n'))
            endpoints_str = '\n        * '.join(str(endpoint) for endpoint in self.active_endpoints(rel_type))
            lines.append(f'    • Endpoints:\n        * {endpoints_str}')

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)

    def __repr__(self) -> str:
        """JSON representation of the knowledge model."""
        model = {
            'extraction_config': json.loads(repr(self.extraction_config)),
            'entity_types': [json.loads(repr(entity_type)) for entity_type in self.active_entity_types.values()],
            'relationship_types': [],
        }
        for rel_type in self.active_relationship_types.values():
            rel_data = json.loads(repr(rel_type))
            rel_data['endpoints'] = [json.loads(repr(endpoint)) for endpoint in self.active_endpoints(rel_type)]
            model['relationship_types'].append(rel_data)
        return json.dumps(model, indent=2, ensure_ascii=False)

    def __post_init__(self) -> None:
        """Validate knowledge model invariants."""
        self._validate_projections()
        self._validate_relationship_endpoints()

    def _validate_projections(self) -> None:
        """Validate that the entity and relationship projections in the extraction config are valid."""
        if self.extraction_config.entity_projection is not None:
            invalid_entities = self.extraction_config.entity_projection - set(self.entity_types.keys())
            if invalid_entities:
                raise ValueError(
                    f'Unknown entity types in projection: {list(invalid_entities)}. The projection must be a subset of the defined entity types.',
                )
        if self.extraction_config.relationship_projection is not None:
            invalid_relationships = self.extraction_config.relationship_projection - set(self.relationship_types.keys())
            if invalid_relationships:
                raise ValueError(
                    f'Unknown relationship types in projection: {list(invalid_relationships)}. The projection must be a subset of the defined relationship types.',
                )

    def _validate_relationship_endpoints(self) -> None:
        """Validate that all relationship endpoints reference valid entity types."""
        valid_entity_types = set(self.entity_types.keys())
        for relationship_type in self.relationship_types.values():
            for endpoint in relationship_type.endpoints:
                if endpoint.source not in valid_entity_types:
                    raise ValueError(
                        f'Relationship type "{relationship_type.name}" has invalid source entity type "{endpoint.source}" in its endpoints.',
                    )
                if endpoint.target not in valid_entity_types:
                    raise ValueError(
                        f'Relationship type "{relationship_type.name}" has invalid target entity type "{endpoint.target}" in its endpoints.',
                    )

    @property
    def active_entity_types(self) -> MappingProxyType[EntityTypeName, EntityType]:
        """Active entity types in the knowledge model projection."""
        if self.extraction_config.entity_projection is None:
            return self.entity_types
        return MappingProxyType(
            {k: v for k, v in self.entity_types.items() if k in self.extraction_config.entity_projection},
        )

    def entity_type(self, name: EntityTypeName) -> EntityType | None:
        """Get an active entity type by name."""
        return self.active_entity_types.get(name)

    def active_endpoints(self, relationship_type: RelationshipType) -> tuple[Endpoint, ...]:
        """Active endpoints for a given relationship type, based on the active entity types in the knowledge model projection."""
        return tuple(
            endpoint
            for endpoint in relationship_type.endpoints
            if self.active_entity_types.keys() >= {endpoint.source, endpoint.target}
        )

    @property
    def active_relationship_types(self) -> MappingProxyType[RelationshipTypeName, RelationshipType]:
        """Active relationship types in the knowledge model projection."""
        projected_relationship_types = self.relationship_types
        if self.extraction_config.relationship_projection is not None:
            projected_relationship_types = {
                k: v for k, v in self.relationship_types.items() if k in self.extraction_config.relationship_projection
            }
        return MappingProxyType({k: v for k, v in projected_relationship_types.items() if self.active_endpoints(v)})

    def relationship_type(self, name: RelationshipTypeName) -> RelationshipType | None:
        """Get an active relationship type by name."""
        return self.active_relationship_types.get(name)
