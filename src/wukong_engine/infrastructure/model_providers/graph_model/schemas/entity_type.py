from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .field import FieldSchema


# TODO: Better class docstring that explains attributes
class EntityTypeSchema(BaseModel):
    """Schema-level representation of an entity type definition."""

    name: str  # TODO: Pass from data model schema
    parameters: dict[str, Any]  # TODO: Validate, decide if flatten or dict
    input_document_groups: dict[str, list[str]] = Field(default_factory=dict)  # TODO: Change name and check
    fields: list[FieldSchema]  # TODO: Check

    # Disable type coercion
    model_config = ConfigDict(strict=True)

    @field_validator('input_document_groups', mode='before')
    @classmethod
    def parse_input_document_groups(cls, v: Any) -> Any:
        """Parse context level -> document groups mappings."""
        # Canonical context level mappings
        if isinstance(v, dict):
            input_doc_groups = {}
            for k, val in v.items():
                if isinstance(val, str):  # Single document set
                    input_doc_groups[k] = [val]
                else:  # Multiple document sets or invalid input
                    input_doc_groups[k] = val

        # Return raw value
        return v

    @field_validator('fields', mode='before')
    @classmethod
    def parse_fields(cls, v: Any) -> Any:
        """Parse field mappings."""
        # Validate field mappings and inject field names
        if isinstance(v, dict):
            fields = []
            for field_name, field_data in v.items():
                if not isinstance(field_data, dict):
                    fields.append({'name': field_name})  # Invalid field data, will be caught later
                fields.append({'name': field_name, **field_data})
            return fields

        # Return raw value
        return v

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
