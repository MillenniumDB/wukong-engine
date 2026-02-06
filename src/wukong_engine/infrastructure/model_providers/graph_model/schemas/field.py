import re
from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator

from wukong_engine.core.graph.model.values import ContextLevel, DataType, RetrievalMode


class FieldSchema(BaseModel):
    """Schema-level representation of a field definition."""

    data_type: DataType
    description: StrictStr
    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    options: list[StrictStr] | StrictStr = Field(default_factory=list)
    examples: list[StrictStr] | StrictStr = Field(default_factory=list)
    regex: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    default_value: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    retrieval_mode: dict[ContextLevel, RetrievalMode] | RetrievalMode = Field(default_factory=dict)
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

    @field_validator('instructions', 'regex', 'default_value', 'retrieval_mode', mode='before')
    @classmethod
    def parse_context_level_mappings(cls, value: Any) -> Any:
        """Parse context level -> string mappings."""
        if isinstance(value, str):  # Apply same value to all context levels
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('options', 'examples', mode='before')
    @classmethod
    def parse_value_lists(cls, value: Any) -> Any:
        """Parse lists containing string values."""
        if isinstance(value, str):  # Single string value gets converted to single-item list
            return [value]
        return value

    @field_validator('regex')
    @classmethod
    def validate_regex(cls, value: dict[ContextLevel, str]) -> dict[ContextLevel, str]:
        """Validate the provided regex patterns."""
        for context_level, pattern in value.items():
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(
                    f'Invalid regex pattern "{pattern}" for context level "{context_level}": {error}',
                ) from error
        return value
