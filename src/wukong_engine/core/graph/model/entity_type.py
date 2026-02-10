from dataclasses import dataclass
from types import MappingProxyType

from .field import Field
from .values import ContextLevel, FieldName


@dataclass(frozen=True)
class EntityType:
    """An entity type from the graph model."""

    description: str
    instructions: MappingProxyType[ContextLevel, str]
    primary_key: FieldName
    fields: MappingProxyType[FieldName, Field]
    document_groups: MappingProxyType[ContextLevel, tuple[str, ...]]
    # TODO: Duplicates

    def __post_init__(self) -> None:
        """Validate entity type invariants."""
        self._validate_primary_key()

    def _validate_primary_key(self) -> None:
        """Validate that the primary key is defined in the fields."""
        if self.primary_key not in self.fields:
            raise ValueError(f'Invalid EntityType: primary key "{self.primary_key}" not found in fields')


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
