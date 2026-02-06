from dataclasses import dataclass
from types import MappingProxyType

from .field import Field
from .values import ContextLevel, EntityTypeName

# TODO: Required: Primary key restriction over required field attribute
# TODO: Complete


@dataclass(frozen=True)
class EntityType:
    """An entity type from the graph model."""

    name: EntityTypeName
    document_groups: MappingProxyType[ContextLevel, tuple[str, ...]]
    fields: tuple[Field, ...]


# TODO: Complete
# class EntityType:
#     """An entity type from the data model.

#     Attributes:
#         name: The name of the entity type.
#         parameters: The parameters section from the entity type definition.
#         sources: The sources section from the entity type definition.
#         fields: The fields section from the entity type definition.
#     """

#     def __init__(self, name: str, entity_data: dict[str, Any]) -> None:
#         """Initialize an EntityType instance.

#         Args:
#             name: The name of the entity type.
#             entity_data: The entity data from the data model JSON.
#         """
#         self.name = name
#         self.parameters = entity_data.get('parameters', {})
#         self.sources = entity_data.get('input_document_groups', {})
#         self._fields = [Field(f_name, f_data) for f_name, f_data in entity_data.get('fields', {}).items()]
#         self._validate_data(entity_data)

#     def __repr__(self) -> str:
#         """Return a string representation of the entity type."""
#         return f'EntityType(name={self.name!r}, parameters={self.parameters!r}, sources={self.sources!r}, fields={self._fields!r})'

#     def __str__(self) -> str:
#         """Return a human-readable string representation of the entity type."""
#         return f'EntityType: {self.name}'

#     def _validate_data(self, entity_data: dict[str, Any]) -> None:
#         """Validate the entity type to ensure it meets all requirements.

#         Args:
#             entity_data: The entity type data to validate.

#         Raises:
#             ValueError: If the entity type does not meet all requirements.
#         """
#         # Skip validation for special entities
#         if self.parameters.get('special_entity', False):
#             return

#         # Naming conventions
#         if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', self.name):
#             raise ValueError(
#                 f'Invalid entity name "{self.name}". Entity names must start with a letter and contain only alphanumeric characters.',
#             )
#         if self.name.lower() in ('document', 'chunk'):
#             raise ValueError(f'Entity name "{self.name}" is reserved for special entities and cannot be used')

#         # Top-level sections
#         sections = ['parameters', 'sources', 'fields']
#         for section in sections:
#             if section not in entity_data or not isinstance(entity_data[section], dict):
#                 raise ValueError(f'Entity type "{self.name}" must have a valid "{section}" section')

#         # Specific sections
#         self._validate_parameters()
#         self._validate_sources()
#         self._validate_fields()

#     def _validate_parameters(self) -> None:
#         """Validate entity type parameters to ensure they meet all requirements.

#         Raises:
#             ValueError: If any parameter does not meet all requirements.
#         """
#         # Mandatory parameters
#         mandatory_parameters = ['description', 'primary_key']
#         for parameter in mandatory_parameters:
#             if parameter not in self.parameters:
#                 raise ValueError(
#                     f'Entity type "{self.name}" must have a valid "{parameter}" field in the parameters section',
#                 )

#         # Primary key
#         if self.parameters['primary_key'] not in self.fields:
#             raise ValueError(
#                 f'The specified primary key field "{self.parameters["primary_key"]}" for entity type "{self.name}" does not exist',
#             )

#     def _validate_sources(self) -> None:
#         """Validate entity type sources to ensure they meet all requirements.

#         Raises:
#             ValueError: If any source does not meet all requirements.
#         """
#         # Sources
#         for source, doc_sets in self.sources.items():
#             if source not in ('chunk', 'document'):
#                 raise ValueError(
#                     f'Invalid source "{source}" for entity type "{self.name}". Sources must be among: "chunk", "document".',
#                 )
#             if not isinstance(doc_sets, list):
#                 raise TypeError(f'Source "{source}" for entity type "{self.name}" must be a list of document sets')

#         # TODO: Source modes for each field
#         for field_name, field_data in self.fields.items():
#             if 'description' not in field_data:
#                 raise ValueError(
#                     f'Field "{field_name}" for entity type "{self.name}" must have a valid "description" attribute',
#                 )

#     def _validate_fields(self) -> None:
#         """Validate entity type fields to ensure they meet all requirements.

#         Raises:
#             ValueError: If any field does not meet all requirements.
#         """
#         # Naming conventions
#         for field_name in self.fields:
#             if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', field_name):
#                 raise ValueError(
#                     f'Invalid field name "{field_name}" for entity type "{self.name}". Field names must start with a letter and contain only alphanumeric characters and underscores.',
#                 )
#             if field_name.lower() == 'extracted_from':
#                 raise ValueError(
#                     f'Field name "{field_name}" for entity type "{self.name}" is reserved for special fields and cannot be used',
#                 )

#         # Mandatory fields
#         for field_name, field_data in self.fields.items():
#             if 'description' not in field_data:
#                 raise ValueError(
#                     f'Field "{field_name}" for entity type "{self.name}" must have a valid "description" attribute',
#                 )

#         # Primary key is required
#         if not self.fields[self.parameters['primary_key']].get('required', True):
#             raise ValueError(
#                 f'The primary key field "{self.parameters["primary_key"]}" for entity type "{self.name}" must have the "required" attribute set to true.',
#             )

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

#     # TODO: Complete
#     @property
#     def extraction_fields(self, source: str) -> list[Field]:
#         """A dictionary containing the extraction fields for each source of the entity type."""
#         return self.fields(source, FieldMode.EXTRACTION)

#     # TODO: Complete
#     @property
#     def external_fields(self, source: str) -> dict[str, Any]:
#         """A dictionary containing the external fields of the entity type."""
#         return {k: v for k, v in self.fields.items() if v.get('external', False)}

#     # TODO: Complete
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
