"""Graph model field classes."""

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.rules.compatibility import ensure_compatible_retrieval_modes
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.shared import RegexPattern

from .values import DataType, FieldName, MergeStrategy


@dataclass(frozen=True)
class _Field:
    """Base field class for entity and relationship types."""

    name: FieldName
    data_type: DataType
    description: str
    options: tuple[str, ...]
    examples: tuple[str, ...]
    required: bool
    merge_strategy: MergeStrategy | None

    def __str__(self) -> str:
        """User-friendly string representation of the field."""
        return f'{self.name}: {self.description} [{self.data_type.value}]'

    def __repr__(self) -> str:
        """JSON representation of the field."""
        field_info: dict[str, Any] = {
            'name': str(self.name),
            'data_type': self.data_type.value,
            'description': self.description,
        }
        if self.options:
            field_info['options'] = list(self.options)
        if self.examples:
            field_info['examples'] = list(self.examples)
        return json.dumps(field_info)


@dataclass(frozen=True, repr=False)
class EntityField(_Field):
    """A field from an entity type."""

    instructions: MappingProxyType[ContextLevel, str] = field(compare=False, hash=False)
    regex: MappingProxyType[ContextLevel, RegexPattern] = field(compare=False, hash=False)
    default_value: MappingProxyType[ContextLevel, str] = field(compare=False, hash=False)
    retrieval_mode: MappingProxyType[ContextLevel, EntityRetrievalMode] = field(compare=False, hash=False)

    def __post_init__(self) -> None:
        """Validate entity field invariants."""
        self._validate_default_values()
        self._validate_retrieval_mode()
        self._validate_examples()

    def _validate_default_values(self) -> None:
        """Validate that default values are consistent with field rules."""
        # For context levels that use DEFAULT retrieval mode, a default value must be explicitly defined
        for ctx_level, ret_mode in self.retrieval_mode.items():
            if ret_mode == EntityRetrievalMode.DEFAULT and self.default_value.get(ctx_level) is None:
                raise ValueError(
                    f'Invalid EntityField "{self.name}": Context level '
                    f'"{ctx_level.value}" uses DEFAULT retrieval mode but there is '
                    f'no default value explicitly defined for that context level',
                )

        for ctx_level, def_val in self.default_value.items():
            # Allowed values must be respected when options are defined
            if self.options and def_val not in self.options:
                raise ValueError(
                    f'Invalid EntityField "{self.name}": Default value "{def_val}" '
                    f'for context level "{ctx_level.value}" is not present in the field\'s '
                    f'defined options: {self.options}',
                )

            # Regex pattern must be respected when defined
            pattern = self.regex.get(ctx_level)
            if pattern is not None and not pattern.match(def_val):
                raise ValueError(
                    f'Invalid EntityField "{self.name}": Default value "{def_val}" '
                    f'for context level "{ctx_level.value}" does not match the '
                    f'specified regex pattern: {pattern.pattern}',
                )

    def _validate_retrieval_mode(self) -> None:
        """Validate that the retrieval mode is properly defined."""
        try:
            ensure_compatible_retrieval_modes(self.retrieval_mode)
        except ValueError as error:
            raise ValueError(f'Invalid EntityField "{self.name}": {error}') from error

    def _validate_examples(self) -> None:
        """Validate that examples are consistent with field rules."""
        if not self.examples:
            return

        # Allowed values must be respected when options are defined
        for example in self.examples:
            if self.options and example not in self.options:
                raise ValueError(
                    f'Invalid EntityField "{self.name}": Example "{example}" '
                    f"is not present in the field's defined options: {self.options}",
                )

        # Regex pattern must be respected when defined
        for ctx_level, pattern in self.regex.items():
            for example in self.examples:
                if not pattern.match(example):
                    raise ValueError(
                        f'Invalid EntityField "{self.name}": Example "{example}" '
                        f'does not match the specified regex pattern for '
                        f'context level "{ctx_level.value}": {pattern.pattern}',
                    )


@dataclass(frozen=True, repr=False)
class RelationshipField(_Field):
    """A field from a relationship type."""

    instructions: str | None
    regex: RegexPattern | None
    default_value: str | None
    retrieval_mode: RelationshipRetrievalMode

    def __post_init__(self) -> None:
        """Validate relationship field invariants."""
        self._validate_default_value()
        self._validate_examples()

    def _validate_default_value(self) -> None:
        """Validate that the default value is consistent with field rules."""
        # For fields that use DEFAULT retrieval mode, a default value must be explicitly defined
        if self.retrieval_mode == RelationshipRetrievalMode.DEFAULT and self.default_value is None:
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": DEFAULT retrieval mode requires an explicit non-null default value',
            )

        # Allowed values must be respected when options are defined
        if self.options and self.default_value is not None and self.default_value not in self.options:
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": Default value "{self.default_value}" '
                f"is not present in the field's defined options: {self.options}",
            )

        # Regex pattern must be respected when defined
        if self.regex is not None and self.default_value is not None and not self.regex.match(self.default_value):
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": Default value "{self.default_value}" '
                f'does not match the specified regex pattern: {self.regex.pattern}',
            )

    def _validate_examples(self) -> None:
        """Validate that examples are consistent with field rules."""
        if not self.examples:
            return

        # Allowed values must be respected when options are defined
        if self.options:
            for example in self.examples:
                if example not in self.options:
                    raise ValueError(
                        f'Invalid RelationshipField "{self.name}": Example "{example}" '
                        f"is not present in the field's defined options: {self.options}",
                    )

        # Regex pattern must be respected when defined
        if self.regex is not None:
            for example in self.examples:
                if not self.regex.match(example):
                    raise ValueError(
                        f'Invalid RelationshipField "{self.name}": Example "{example}" '
                        f'does not match the specified regex pattern: {self.regex.pattern}',
                    )
