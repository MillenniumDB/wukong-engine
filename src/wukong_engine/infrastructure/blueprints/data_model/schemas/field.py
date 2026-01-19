from typing import Any, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wukong_engine.infrastructure.blueprints.data_model.tokens import ContentLevelToken, FieldModeToken, FieldTypeToken


class FieldSchema(BaseModel):
    """Schema-level representation of a field definition."""

    name: str
    data_type: FieldTypeToken
    description: str
    instructions: dict[ContentLevelToken, str] = Field(default_factory=dict)
    options: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    regex: dict[ContentLevelToken, str] = Field(default_factory=dict)
    default_value: dict[ContentLevelToken, str] = Field(default_factory=dict)
    mode: dict[ContentLevelToken, FieldModeToken] = Field(default_factory=dict)
    required: bool = False

    # Disable type coercion
    model_config = ConfigDict(strict=True)

    @field_validator('instructions', 'regex', 'default_value', mode='before')
    @classmethod
    def parse_content_level_mappings(cls, v: Any) -> Any:
        """Parse content level -> string mappings."""
        # Apply same value to all content levels
        if isinstance(v, str):
            return dict.fromkeys(get_args(ContentLevelToken), v)

        # Canonical content level mappings
        if isinstance(v, dict):
            return v

        # Return raw value
        return v

    @field_validator('options', 'examples', mode='before')
    @classmethod
    def parse_value_lists(cls, v: Any) -> Any:
        """Parse lists containing string values."""
        # Single string value gets converted to single-item list
        if isinstance(v, str):
            return [v]

        # Canonical list of strings
        if isinstance(v, list):
            return v

        # Return raw value
        return v

    @field_validator('mode', mode='before')
    @classmethod
    def parse_mode(cls, v: Any) -> Any:
        """Parse content level -> field mode mappings."""
        # Apply same field mode to all content levels
        if isinstance(v, str):
            return dict.fromkeys(get_args(ContentLevelToken), v)

        # Canonical content level mappings
        if isinstance(v, dict):
            return v

        # Return raw value
        return v
