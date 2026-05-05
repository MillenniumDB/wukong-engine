import json
from dataclasses import dataclass
from types import MappingProxyType

from wukong_engine.core.documents.model.values import DocumentCollectionName
from wukong_engine.core.extraction.model.values import ContextLevel

from .field import EntityField
from .values import EntityIdentityPolicy, EntityTypeName, FieldName, MergeStrategy


@dataclass(frozen=True)
class EntityType:
    """An entity type from the graph model."""

    name: EntityTypeName
    description: str
    instructions: MappingProxyType[ContextLevel, str]
    primary_key: FieldName
    identity_policy: EntityIdentityPolicy
    fields: MappingProxyType[FieldName, EntityField]
    document_collections: MappingProxyType[ContextLevel, tuple[DocumentCollectionName, ...]]
    default_merge_strategy: MergeStrategy

    def __str__(self) -> str:
        """User-friendly string representation of the entity type."""
        lines = []
        lines.append(str(self.name))
        lines.append(f'  • Description: {self.description}')
        lines.append(f'  • Primary Key: {self.primary_key}')
        lines.append(f'  • Identity Policy (Deduplication): {self.identity_policy.value}')
        lines.append(f'  • Fields: {len(self.fields)}')
        lines.append(f'      * {"\n      * ".join(str(field) for field in self.fields.values())}')

        # Document collections per context level
        doc_collections = []
        for context_level, collections in self.document_collections.items():
            if collections:
                doc_collections.append(f'{context_level.value} [{", ".join(str(c) for c in collections)}]')
        if doc_collections:
            lines.append(f'  • Document Collections: {", ".join(doc_collections)}')
        else:
            lines.append('  • Document Collections: NONE')

        return '\n'.join(lines)

    def __repr__(self) -> str:
        """JSON representation of the entity type."""
        entity_info = {
            'name': str(self.name),
            'description': self.description,
            'primary_key': str(self.primary_key),
            'fields': [json.loads(repr(field)) for field in self.fields.values()],
        }
        return json.dumps(entity_info)

    def __post_init__(self) -> None:
        """Validate entity type invariants."""
        self._validate_primary_key()
        self._validate_document_collections()

    def _validate_primary_key(self) -> None:
        """Validate that the primary key is defined in the fields."""
        if self.primary_key not in self.fields:
            raise ValueError(f'Invalid EntityType "{self.name}": primary key "{self.primary_key}" not found in fields')

    def _validate_document_collections(self) -> None:
        """Validate that there are no duplicated document collection names."""
        for context_level, collections in self.document_collections.items():
            if len(collections) != len(set(collections)):
                duplicates = {c for c in collections if collections.count(c) > 1}
                raise ValueError(
                    f'Invalid EntityType "{self.name}": duplicate document collection names found '
                    f'for context level "{context_level.value}": {duplicates}',
                )


# TODO: Check later when extracting
#     def is_special_entity(self) -> bool:
#         """Check if the entity type is a special entity.

#         Returns:
#             True if the entity type is a special entity, False otherwise.
#         """
#         return self.parameters.get('special_entity', False)

#     def has_content_level(self, level: ContentLevel) -> bool:
#         """Check if the entity type has a specific source.

#         Args:
#             level: The source to check.

#         Returns:
#             True if the entity type has the specified source, False otherwise.
#         """
#         return level.value in self.sources

#     def source_documents(self, source: str) -> set[str]:
#         """Get the document sets associated with a specific source.

#         Args:
#             source: The source to get document sets for.

#         Returns:
#             A set of document dataset names associated with the specified source.
#         """
#         return set(self.sources.get(source, []))

#     def fields(self, source: ContentLevel | None = None, field_mode: FieldMode | None = None) -> list[Field]:
#         """Get the fields for a specific source and field mode.

#         Args:
#             source: The source to get fields for. If None, all sources are considered.
#             field_mode: The field mode to filter fields by. If None, all field modes are considered.

#         Returns:
#             A list of Field objects for the specified source and field mode.
#         """
#         result = []
#         for field in self._fields:
#             pass

#         return result

#     @property
#     def extraction_fields(self, source: str) -> list[Field]:
#         """A dictionary containing the extraction fields for each source of the entity type."""
#         return self.fields(source, FieldMode.EXTRACTION)

#     @property
#     def external_fields(self, source: str) -> dict[str, Any]:
#         """A dictionary containing the external fields of the entity type."""
#         return {k: v for k, v in self.fields.items() if v.get('external', False)}

#     @property
#     def default_fields(self, source: str) -> dict[str, Any]:
#         """A dictionary containing the default fields of the entity type."""
#         entity_pk = self.parameters.get('primary_key', '')

#         # Hybrid entities prioritize hybrid fields over placeholders
#         if self.has_source(Source.CHUNK) and self.has_source(Source.DOCUMENT):
#             return {
#                 k: v
#                 for k, v in self.fields.items()
#                 if 'constant' in v and k != entity_pk and not v.get('hybrid', False)
#             }

#         # Other entities prioritize metadata over placeholders
#         return {
#             k: v for k, v in self.fields.items() if 'constant' in v and k != entity_pk and k not in self.external_fields
#         }
