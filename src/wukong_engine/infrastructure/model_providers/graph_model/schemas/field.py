import re
from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator

from wukong_engine.core.graph.model.values import (
    ContextLevel,
    DataType,
    EntityRetrievalMode,
    RelationshipRetrievalMode,
)


class _FieldSchema(BaseModel):
    """Base schema for field definitions."""

    data_type: DataType
    description: StrictStr
    options: list[StrictStr] | StrictStr = Field(default_factory=list)
    examples: list[StrictStr] | StrictStr = Field(default_factory=list)
    required: StrictBool = False

    # Mapping of various string representations to DataType members
    _DATA_TYPE_ALIASES: ClassVar[dict[str, DataType]] = {
        'str': DataType.STRING,
        'string': DataType.STRING,
        'text': DataType.STRING,
        # 'int': DataType.INTEGER,
        # 'integer': DataType.INTEGER,
        # 'number': DataType.INTEGER,
        # 'float': DataType.FLOAT,
        # 'double': DataType.FLOAT,
        # 'bool': DataType.BOOLEAN,
        # 'boolean': DataType.BOOLEAN,
    }

    @field_validator('data_type', mode='before')
    @classmethod
    def normalize_data_type(cls, value: Any) -> Any:
        """Normalize data type strings to DataType members."""
        if isinstance(value, str):
            return cls._DATA_TYPE_ALIASES.get(value, value)
        return value

    @field_validator('options', 'examples')
    @classmethod
    def normalize_value_lists(cls, value: list[str] | str) -> list[str]:
        """Normalize lists containing string values."""
        if isinstance(value, str):
            return [value]
        return value


class EntityFieldSchema(_FieldSchema):
    """Schema-level representation of an entity field definition."""

    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    regex: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    default_value: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    retrieval_mode: dict[ContextLevel, EntityRetrievalMode] | EntityRetrievalMode = Field(default_factory=dict)

    @field_validator('instructions', 'default_value')
    @classmethod
    def normalize_context_level_mappings(cls, value: dict[ContextLevel, str] | str) -> dict[ContextLevel, str]:
        """Normalize context level -> string mappings."""
        if isinstance(value, str):
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('regex')
    @classmethod
    def normalize_and_validate_regex(cls, value: dict[ContextLevel, str] | str) -> dict[ContextLevel, str]:
        """Normalize and validate the provided regex patterns."""
        if isinstance(value, str):
            value = dict.fromkeys(ContextLevel, value)
        for context_level, pattern in value.items():
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(
                    f'Invalid regex pattern "{pattern}" for context level "{context_level}": {error}',
                ) from error
        return value

    @field_validator('retrieval_mode')
    @classmethod
    def normalize_retrieval_mode(
        cls,
        value: dict[ContextLevel, EntityRetrievalMode] | EntityRetrievalMode,
    ) -> dict[ContextLevel, EntityRetrievalMode]:
        """Normalize retrieval mode mapping."""
        if isinstance(value, EntityRetrievalMode):
            return dict.fromkeys(ContextLevel, value)
        return value


class RelationshipFieldSchema(_FieldSchema):
    """Schema-level representation of a relationship field definition."""

    instructions: StrictStr | None = None
    regex: StrictStr | None = None
    default_value: StrictStr | None = None
    retrieval_mode: RelationshipRetrievalMode = RelationshipRetrievalMode.EXTRACT

    @field_validator('regex')
    @classmethod
    def validate_regex(cls, value: str | None) -> str | None:
        """Validate the provided regex pattern."""
        if value is not None:
            try:
                re.compile(value)
            except re.error as error:
                raise ValueError(f'Invalid regex pattern "{value}": {error}') from error
        return value
