from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .field import FieldSchema


class EntityTypeSchema(BaseModel):
    """Schema-level representation of an entity type definition."""

    model_config = ConfigDict(strict=True)  # Disable type coercion

    name: str  # TODO: Pass from data model schema
    parameters: dict[str, Any]  # TODO: Validate, decide if flatten or dict
    # TODO: Validate existence of document groups in documents.json
    input_document_groups: dict[ContentLevel, list[str] | None]
    fields: list[FieldSchema]  # TODO: Required: Primary key restriction over required field attribute

    @field_validator('input_document_groups', mode='before')
    @classmethod
    def parse_input_document_groups(cls, v: Any) -> dict[ContentLevel, list[str] | None]:
        """Parse content level to document groups mappings."""
        # Consider specific document sets per source
        if isinstance(v, dict):
            # Start with NULL values as default for all sources
            sources = dict.fromkeys(ContentLevel, None)

            # Parse the specified dictionary
            for k, val in v.items():
                if isinstance(val, str):  # Single document set
                    sources[ContentLevel.from_string(k)] = [val]
                elif isinstance(val, list):  # Multiple document sets
                    for item in val:
                        if not isinstance(item, str):
                            raise TypeError('All document set names must be strings')
                    sources[ContentLevel.from_string(k)] = val
                else:
                    raise TypeError('Document set names must be strings or string arrays')
            return sources
        raise TypeError('Expected a mapping: sources -> document set strings or string arrays')

    @field_validator('fields', mode='before')
    @classmethod
    def parse_fields(cls, v: Any) -> list[dict[str, Any]]:
        """Parse field mappings."""
        # Validate field mappings and inject field names
        if isinstance(v, dict):
            fields = []
            for field_name, field_data in v.items():
                if not isinstance(field_data, dict):
                    raise TypeError(f'Field "{field_name}" must map to an object')
                fields.append({'name': field_name, **field_data})
            return fields
        raise TypeError('Expected a mapping of field names to field data')

    @model_validator(mode='after')
    def validate_field_modes(self) -> Self:
        """Validate that all chosen field modes are compatible with their respective sources."""
        for field in self.fields:
            for source, mode in field.mode.items():
                valid_modes = CONTENT_MODES.get(source, set())
                if mode not in valid_modes:
                    raise ValueError(
                        f'Field "{field.name}": Mode "{mode}" is not a valid field mode for source "{source}"',
                    )
        return self
