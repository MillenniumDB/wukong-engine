"""Pydantic schemas for entity and relationship field definitions."""

import re
from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.knowledge.model.values import DataType, MergeStrategy


class _FieldSchema(BaseModel):
    """Base schema for field definitions.

    Attributes:
        data_type: Data type of the field's values; accepts aliases such as "str" or "text".
        description: Description of what the field holds.
        options: Allowed values for the field; a single string is turned into a one-item list.
        examples: Example values for the field; a single string is turned into a one-item list.
        required: Whether the field must be present in extracted objects.
        merge_strategy: How to merge values when deduplicating, or None to use the type's default. Accepts aliases
            such as "overwrite" or "first".
    """

    data_type: DataType
    description: StrictStr
    options: list[StrictStr] | StrictStr = Field(default_factory=list)
    examples: list[StrictStr] | StrictStr = Field(default_factory=list)
    required: StrictBool = False
    merge_strategy: MergeStrategy | None = None

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

    # Mapping of various string representations to MergeStrategy members
    _MERGE_STRATEGY_ALIASES: ClassVar[dict[str, MergeStrategy]] = {
        'keep': MergeStrategy.KEEP,
        'existing': MergeStrategy.KEEP,
        'preserve': MergeStrategy.KEEP,
        'retain': MergeStrategy.KEEP,
        'first': MergeStrategy.KEEP,
        'replace': MergeStrategy.REPLACE,
        'incoming': MergeStrategy.REPLACE,
        'overwrite': MergeStrategy.REPLACE,
        'update': MergeStrategy.REPLACE,
        'last': MergeStrategy.REPLACE,
        'longest': MergeStrategy.LONGEST,
        'verbose': MergeStrategy.LONGEST,
        'complete': MergeStrategy.LONGEST,
        'shortest': MergeStrategy.SHORTEST,
        'concise': MergeStrategy.SHORTEST,
        'minimal': MergeStrategy.SHORTEST,
    }

    @field_validator('data_type', mode='before')
    @classmethod
    def normalize_data_type(cls, value: Any) -> Any:
        """Normalize data type strings to DataType members.

        Args:
            value: Raw input for the ``data_type`` field.

        Returns:
            The matching DataType member if ``value`` is a known alias, otherwise ``value`` unchanged for regular
            validation.
        """
        if isinstance(value, str):
            return cls._DATA_TYPE_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('merge_strategy', mode='before')
    @classmethod
    def normalize_merge_strategy(cls, value: Any) -> Any:
        """Normalize merge strategy strings to MergeStrategy members.

        Args:
            value: Raw input for the ``merge_strategy`` field.

        Returns:
            The matching MergeStrategy member if ``value`` is a known alias, otherwise ``value`` unchanged for
            regular validation.
        """
        if isinstance(value, str):
            return cls._MERGE_STRATEGY_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('options', 'examples')
    @classmethod
    def normalize_value_lists(cls, value: list[str] | str) -> list[str]:
        """Normalize lists containing string values.

        Args:
            value: Validated list of strings, or a single string.

        Returns:
            ``value`` wrapped in a list if it's a single string, otherwise ``value`` unchanged.
        """
        if isinstance(value, str):
            return [value]
        return value


class EntityFieldSchema(_FieldSchema):
    """Schema-level representation of an entity field definition.

    Attributes:
        instructions: Extra extraction instructions per context level; a single string applies to all levels.
        regex: Regex pattern that values must match, per context level; a single string applies to all levels.
        default_value: Default value per context level; a single string applies to all levels.
        retrieval_mode: How the field's value is obtained, per context level; a single mode applies to all levels.
    """

    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    regex: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    default_value: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    retrieval_mode: dict[ContextLevel, EntityRetrievalMode] | EntityRetrievalMode = Field(default_factory=dict)

    @field_validator('instructions', 'default_value')
    @classmethod
    def normalize_context_level_mappings(cls, value: dict[ContextLevel, str] | str) -> dict[ContextLevel, str]:
        """Normalize context level -> string mappings.

        Args:
            value: Validated mapping from context level to string, or a single string.

        Returns:
            A mapping of every context level to ``value`` if it's a single string, otherwise ``value`` unchanged.
        """
        if isinstance(value, str):
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('regex')
    @classmethod
    def normalize_and_validate_regex(cls, value: dict[ContextLevel, str] | str) -> dict[ContextLevel, str]:
        """Normalize and validate the provided regex patterns.

        Args:
            value: Validated mapping from context level to regex pattern, or a single pattern.

        Returns:
            A mapping from context level to pattern, with a single pattern applied to every context level.

        Raises:
            ValueError: If any pattern fails to compile.
        """
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
        """Normalize retrieval mode mapping.

        Args:
            value: Validated mapping from context level to retrieval mode, or a single mode.

        Returns:
            A mapping of every context level to ``value`` if it's a single mode, otherwise ``value`` unchanged.
        """
        if isinstance(value, EntityRetrievalMode):
            return dict.fromkeys(ContextLevel, value)
        return value


class RelationshipFieldSchema(_FieldSchema):
    """Schema-level representation of a relationship field definition.

    Attributes:
        instructions: Extra extraction instructions for the field, if any.
        regex: Regex pattern that values must match, if any.
        default_value: Default value for the field, if any.
        retrieval_mode: How the field's value is obtained.
    """

    instructions: StrictStr | None = None
    regex: StrictStr | None = None
    default_value: StrictStr | None = None
    retrieval_mode: RelationshipRetrievalMode = RelationshipRetrievalMode.EXTRACT

    @field_validator('regex')
    @classmethod
    def validate_regex(cls, value: str | None) -> str | None:
        """Validate the provided regex pattern.

        Args:
            value: Regex pattern to validate, or None if the field has no pattern.

        Returns:
            ``value`` unchanged.

        Raises:
            ValueError: If the pattern fails to compile.
        """
        if value is not None:
            try:
                re.compile(value)
            except re.error as error:
                raise ValueError(f'Invalid regex pattern "{value}": {error}') from error
        return value
