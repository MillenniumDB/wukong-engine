import re
from typing import Any

from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator

from wukong_engine.core.enums import ContentLevel, DataType, FieldMode


class FieldSchema(BaseModel):
    """Schema-level representation of a field definition."""

    name: StrictStr
    data_type: DataType
    description: StrictStr
    instructions: dict[ContentLevel, str | None] = Field(default_factory=lambda: dict.fromkeys(ContentLevel, None))
    options: list[str] | None = None
    examples: list[str] | None = None
    regex: dict[ContentLevel, str | None] = Field(default_factory=lambda: dict.fromkeys(ContentLevel, None))
    default_value: dict[ContentLevel, str | None] = Field(default_factory=lambda: dict.fromkeys(ContentLevel, None))
    mode: dict[ContentLevel, FieldMode] = Field(
        default_factory=lambda: dict.fromkeys(ContentLevel, FieldMode.EXTRACTION)
    )
    required: StrictBool = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate field naming conventions."""
        # General convention
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', v):
            raise ValueError(
                f'Invalid field name "{v}". Field names must start with a letter and contain only alphanumeric characters and underscores.',
            )

        # Special field names
        if v.lower() == 'extracted_from':
            raise ValueError(f'Field name "{v}" is reserved for special fields and cannot be used')
        return v

    @field_validator('data_type', mode='before')
    @classmethod
    def parse_data_type(cls, v: Any) -> DataType:
        """Parse data type string."""
        # String representation
        if isinstance(v, str):
            return DataType.from_string(v)
        raise TypeError('Expected a string representing a data type')

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description conventions."""
        # Description cannot be empty
        if not v.strip():
            raise ValueError('The "description" attribute cannot be an empty string')
        return v

    @field_validator('instructions', 'regex', 'default_value', mode='before')
    @classmethod
    def parse_source_mappings(cls, v: Any) -> dict[ContentLevel, str | None]:
        """Parse source to string mappings."""
        # Apply string value to all sources
        if isinstance(v, str):
            return dict.fromkeys(ContentLevel, v)

        # Apply specific values per source
        if isinstance(v, dict):
            # Start with NULL values as default for all sources
            sources_mapping = dict.fromkeys(ContentLevel, None)

            # Parse the specified dictionary
            for k, val in v.items():
                # Check that all values are strings
                if not isinstance(val, str):
                    raise TypeError('All values must be strings')
                sources_mapping[ContentLevel.from_string(k)] = val
            return sources_mapping
        raise TypeError('Expected a mapping: source -> string, or a string')

    @field_validator('options', 'examples', mode='before')
    @classmethod
    def parse_value_lists(cls, v: Any) -> list[str]:
        """Parse lists containing string values."""
        # Single string value gets converted to single-item list
        if isinstance(v, str):
            return [v]

        # List of string values
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, str):
                    raise TypeError('All array items must be strings')
            return v
        raise TypeError('Expected a string or string array')

    @field_validator('mode', mode='before')
    @classmethod
    def parse_mode(cls, v: Any) -> dict[ContentLevel, FieldMode]:
        """Parse source to field mode mappings."""
        # Apply same field mode to all sources
        if isinstance(v, str):
            return dict.fromkeys(ContentLevel, FieldMode.from_string(v))

        # Apply specific field modes per source
        if isinstance(v, dict):
            # Start with default extraction mode
            modes = dict.fromkeys(ContentLevel, FieldMode.EXTRACTION)

            # Parse the specified dictionary
            for k, val in v.items():
                # Check that all values are strings
                if not isinstance(val, str):
                    raise TypeError('All field mode values must be strings')
                modes[ContentLevel.from_string(k)] = FieldMode.from_string(val)
            return modes
        raise TypeError('Expected a mapping: source -> field mode, or a string representing a field mode')
