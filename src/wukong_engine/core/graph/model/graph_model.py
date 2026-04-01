"""Provides a graph model interface for the engine.

Classes:
    GraphModel: The graph model containing all entity types.
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
class GraphModel:
    """The graph model containing all entity types."""

    extraction_config: ExtractionConfig
    entity_types: MappingProxyType[EntityTypeName, EntityType]
    relationship_types: MappingProxyType[RelationshipTypeName, RelationshipType]

    def __str__(self) -> str:
        """User-friendly string representation of the graph model."""
        lines = []
        lines.append('=' * 80)
        lines.append(' GRAPH MODEL')
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
        """JSON representation of the graph model."""
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
        """Validate graph model invariants."""
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
        """Active entity types in the graph model projection."""
        if self.extraction_config.entity_projection is None:
            return self.entity_types
        return MappingProxyType(
            {k: v for k, v in self.entity_types.items() if k in self.extraction_config.entity_projection},
        )

    def entity_type(self, name: EntityTypeName) -> EntityType:
        """Get an active entity type by name."""
        entity_type = self.active_entity_types.get(name)
        if entity_type is not None:
            return entity_type
        active_names = list(self.active_entity_types.keys())
        raise ValueError(f'Entity type "{name}" is not active or defined. Active entity types: {active_names}.')

    def active_endpoints(self, relationship_type: RelationshipType) -> tuple[Endpoint, ...]:
        """Active endpoints for a given relationship type, based on the active entity types in the graph model projection."""
        return tuple(
            endpoint
            for endpoint in relationship_type.endpoints
            if self.active_entity_types.keys() >= {endpoint.source, endpoint.target}
        )

    @property
    def active_relationship_types(self) -> MappingProxyType[RelationshipTypeName, RelationshipType]:
        """Active relationship types in the graph model projection."""
        projected_relationship_types = self.relationship_types
        if self.extraction_config.relationship_projection is not None:
            projected_relationship_types = {
                k: v for k, v in self.relationship_types.items() if k in self.extraction_config.relationship_projection
            }
        return MappingProxyType({k: v for k, v in projected_relationship_types.items() if self.active_endpoints(v)})

    def relationship_type(self, name: RelationshipTypeName) -> RelationshipType:
        """Get an active relationship type by name."""
        relationship_type = self.active_relationship_types.get(name)
        if relationship_type is not None:
            return relationship_type
        active_names = list(self.active_relationship_types.keys())
        raise ValueError(
            f'Relationship type "{name}" is not active or defined. Active relationship types: {active_names}.',
        )


# class GraphModelOld:
#     """The graph model manager for the WUKONG engine.

#     Loads and validates the graph model, providing easy access to its components.
#     The graph model is loaded once and assumed to be immutable for the duration of the program.
#     """

#     def _load_model(self, graph_model_path: Path) -> None:
#         """Load the graph model from a JSON file, making sure it has a valid format and satisfies all requirements.

#         Args:
#             graph_model_path: The path to the JSON graph model file.

#         Raises:
#             FileNotFoundError: If the graph model file does not exist.
#             ValueError: If the graph model file has an invalid structure or contents.
#         """
#         # Check if the graph model file exists
#         if not graph_model_path.exists():
#             raise FileNotFoundError(f'Graph model file "{graph_model_path}" not found')

#         # Load the graph model
#         try:
#             graph_model = json.loads(
#                 graph_model_path.read_text(encoding='utf-8'),
#                 object_pairs_hook=self._no_duplicate_keys_hook,
#             )
#         except json.JSONDecodeError as error:
#             raise ValueError(f'Invalid structure for the graph model in "{graph_model_path}"') from error

#     @staticmethod
#     def _no_duplicate_keys_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
#         """Validate that the provided key/value pairs do not contain duplicate keys.

#         Args:
#             pairs: A list of key/value pairs to validate.

#         Returns:
#             A dictionary containing the key/value pairs if no duplicate keys are found.

#         Raises:
#             ValueError: If duplicate keys are found in the provided pairs.
#         """
#         seen = set()
#         for key, _ in pairs:
#             if key in seen:
#                 raise ValueError(f'Graph model contains duplicate key "{key}"')
#             seen.add(key)
#         return dict(pairs)

#         # TODO: Add special entities
#         special_entities = {
#             'Document': {
#                 'parameters': {
#                     'special_entity': True,
#                     'description': 'Represents a document that was used for the construction of the knowledge graph.',
#                 },
#                 'fields': {
#                     'name': {
#                         'type': 'string',
#                         'description': 'The name of the original document.',
#                     },
#                     'document_set': {
#                         'type': 'string',
#                         'description': 'The name of the document set where the original document is contained.',
#                     },
#                 },
#             },
#             'Chunk': {
#                 'parameters': {
#                     'special_entity': True,
#                     'description': 'Represents a fragment of a document used for the construction of the knowledge graph.',
#                 },
#                 'fields': {
#                     'text': {
#                         'type': 'string',
#                         'description': 'The text contained in the document chunk.',
#                     },
#                 },
#             },
#         }
#         for entity_name, entity_data in special_entities.items():
#             # special_entity_type = EntityType(entity_name, entity_data)
#             # self._entities.append(special_entity_type)
#             pass

#         # TODO: Add special relations
#         special_relations = {
#             'ChunkOf': {
#                 'special_relation': True,
#                 'origin_target': {'Chunk': ['Document']},
#                 'description': 'Connects each chunk to the respective document from which it was extracted.',
#                 'fields': {
#                     'chunk_number': {
#                         'type': 'integer',
#                         'description': 'The number of the chunk within the document (ordered from beginning to end).',
#                     },
#                 },
#             },
#             'ExtractedFrom': {
#                 'special_relation': True,
#                 'origin_target': {'ALL': ['Chunk', 'Document']},
#                 'description': 'Connects each entity to the respective chunk from which it was extracted.',
#             },
#         }
#         self._relations.update(special_relations)

#     @property
#     def parameters(self) -> dict[str, Any]:
#         """A dictionary containing the parameters of the graph model."""
#         return self._parameters

#     # TODO: Refactor
#     @property
#     def entities(self) -> list[EntityType]:
#         """A list of all regular entity types in the graph model (core/hybrid/special entities are excluded)."""
#         return [
#             entity
#             for entity in self._entities
#             if not entity.has_source('document') and not entity.is_special_entity() and not entity.name.startswith('@')
#         ]

#     # TODO: Refactor
#     @property
#     def core_entities(self) -> list[EntityType]:
#         """A list of all core entity types in the graph model."""
#         return [entity for entity in self._entities if entity.has_source('document')]

#     # TODO: Refactor
#     @property
#     def hybrid_entities(self) -> list[EntityType]:
#         """A list of all hybrid entity types in the graph model."""
#         return [entity for entity in self._entities if entity.has_source('chunk') and entity.has_source('document')]

#     # TODO: Refactor
#     @property
#     def special_entities(self) -> list[EntityType]:
#         """A list of all special entity types in the graph model."""
#         return [entity for entity in self._entities if entity.is_special_entity()]

#     # TODO: Refactor
#     @property
#     def relations(self) -> dict[str, Any]:
#         """A dictionary containing all regular relation types in the graph model (special relations are excluded)."""
#         return {k: v for k, v in self._relations.items() if not v.get('special_relation', False)}

#     # TODO: Refactor
#     @property
#     def special_relations(self) -> dict[str, Any]:
#         """A dictionary containing all special relation types in the graph model."""
#         return {k: v for k, v in self._relations.items() if v.get('special_relation', False)}

#     # TODO: Refactor
#     @property
#     def materialized_relations(self) -> dict[str, Any]:
#         """A dictionary containing all materialized relation types between entity type pairs."""
#         return self._materialized_relations

#     # TODO: Refactor
#     def get_relation_data(self, relation_name: str) -> dict[str, Any]:
#         """Get the data fields of a specific relation type.

#         Data fields are those meant to be extracted from the documents.

#         Args:
#             relation_name: The name of the relation type.

#         Returns:
#             A dictionary containing all data fields of the relation type.
#         """
#         relation_info = self._relations.get(relation_name, {})
#         return {
#             k: v
#             for k, v in relation_info.get('fields', {}).items()
#             if k not in self.get_relation_placeholders(relation_name)
#         }

#     # TODO: Refactor
#     def get_relation_placeholders(self, relation_name: str) -> dict[str, Any]:
#         """Get the placeholder fields of a specific relation type.

#         Args:
#             relation_name: The name of the relation type.

#         Returns:
#             A dictionary containing all placeholder fields of the relation type.
#         """
#         relation_info = self._relations.get(relation_name, {})
#         relation_pk = relation_info.get('primary_key', '')
#         relation_props = relation_info.get('fields', {})
#         return {k: v for k, v in relation_props.items() if 'placeholder' in v and k != relation_pk}

#     # TODO: Refactor
#     def get_relation_fields(self, relation_name: str) -> dict[str, Any]:
#         """Get the full fields of a specific relation type.

#         Args:
#             relation_name: The name of the relation type.

#         Returns:
#             A dictionary containing all fields of the relation type.
#         """
#         return self._relations.get(relation_name, {}).get('fields', {})
