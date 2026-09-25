"""Entity types from the knowledge model."""

import json
from dataclasses import dataclass, field
from types import MappingProxyType

from wukong_engine.core.documents.model.values import ContextLevel, DocumentCollectionName
from wukong_engine.core.extraction.model.values import EntityRetrievalMode

from .field import EntityField
from .values import EntityIdentityPolicy, EntityTypeName, FieldName, MergeStrategy


@dataclass(frozen=True, slots=True)
class EntityType:
    """An entity type from the knowledge model.

    Attributes:
        name: Name of the entity type.
        description: Description of what the entity type represents.
        instructions: Extra extraction instructions per context level.
        primary_key: Name of the field used as primary key. It must be a required field retrieved through
            ``EXTRACT`` or ``LOAD`` at every configured context level.
        identity_policy: Policy used to deduplicate entities of this type.
        fields: Field definitions, keyed by field name.
        document_collections: Document collections to extract this entity type from, per context level.
        default_merge_strategy: Merge strategy for fields that don't define their own.
    """

    name: EntityTypeName
    description: str
    instructions: MappingProxyType[ContextLevel, str]
    primary_key: FieldName
    identity_policy: EntityIdentityPolicy
    fields: MappingProxyType[FieldName, EntityField]
    document_collections: MappingProxyType[ContextLevel, tuple[DocumentCollectionName, ...]]
    default_merge_strategy: MergeStrategy

    # Private index for fast retrieval of fields by context level and retrieval mode
    _fields_index: MappingProxyType[ContextLevel, MappingProxyType[EntityRetrievalMode, tuple[EntityField, ...]]] = (
        field(init=False, repr=False)
    )

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
        """Validate entity type invariants and build fields index.

        Raises:
            ValueError: If the primary key is invalid or a context level lists duplicated document collections.
        """
        self._validate_primary_key()
        self._validate_document_collections()
        object.__setattr__(self, '_fields_index', self._build_fields_index())

    def _validate_primary_key(self) -> None:
        """Validate primary key invariants.

        Raises:
            ValueError: If the primary key is not one of the fields, is not required, or uses a retrieval mode other
                than ``EXTRACT`` or ``LOAD`` at some context level.
        """
        # PK existence
        if self.primary_key not in self.fields:
            raise ValueError(f'Invalid EntityType "{self.name}": primary key "{self.primary_key}" not found in fields')

        # PK field must be required
        primary_key_field = self.fields[self.primary_key]
        if not primary_key_field.required:
            raise ValueError(
                f'Invalid EntityType "{self.name}": primary key "{self.primary_key}" must be explicitly marked as required (boolean)',
            )

        # PK retrieval mode must be either EXTRACT or LOAD
        for context_level, retrieval_mode in primary_key_field.retrieval_mode.items():
            if retrieval_mode not in {EntityRetrievalMode.EXTRACT, EntityRetrievalMode.LOAD}:
                raise ValueError(
                    f'Invalid EntityType "{self.name}": primary key "{self.primary_key}" has retrieval mode '
                    f'"{retrieval_mode.value}" for context level "{context_level.value}", expected "extract" or "load"',
                )

    def _validate_document_collections(self) -> None:
        """Validate that there are no duplicated document collection names.

        Raises:
            ValueError: If a context level lists the same document collection more than once.
        """
        for context_level, collections in self.document_collections.items():
            if len(collections) != len(set(collections)):
                duplicates = {c for c in collections if collections.count(c) > 1}
                raise ValueError(
                    f'Invalid EntityType "{self.name}": duplicate document collection names found '
                    f'for context level "{context_level.value}": {duplicates}',
                )

    def _build_fields_index(
        self,
    ) -> MappingProxyType[ContextLevel, MappingProxyType[EntityRetrievalMode, tuple[EntityField, ...]]]:
        """Precompute fields by context level and retrieval mode for fast lookups.

        Fields without a retrieval mode for a context level are indexed under ``EXTRACT`` for that level.

        Returns:
            Read-only mapping from context level to retrieval mode to the fields using that mode, in definition
            order.
        """
        index: dict[ContextLevel, dict[EntityRetrievalMode, list[EntityField]]] = {}
        for entity_field in self.fields.values():
            for context_level in ContextLevel:
                retrieval_mode = entity_field.retrieval_mode.get(context_level, EntityRetrievalMode.EXTRACT)
                by_mode = index.setdefault(context_level, {})
                by_mode.setdefault(retrieval_mode, []).append(entity_field)
        return MappingProxyType(
            {
                context_level: MappingProxyType(
                    {retrieval_mode: tuple(entity_fields) for retrieval_mode, entity_fields in by_mode.items()},
                )
                for context_level, by_mode in index.items()
            },
        )

    def fields_for(self, context_level: ContextLevel, retrieval_mode: EntityRetrievalMode) -> tuple[EntityField, ...]:
        """Get the relevant fields for a specific context level and retrieval mode.

        Args:
            context_level: Context level to look up.
            retrieval_mode: Retrieval mode the fields must use at that context level.

        Returns:
            The matching fields in definition order, or an empty tuple if there are none.
        """
        return self._fields_index.get(context_level, {}).get(retrieval_mode, ())
