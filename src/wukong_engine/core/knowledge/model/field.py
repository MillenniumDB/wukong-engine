"""Knowledge model field classes."""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.rules.compatibility import ensure_compatible_retrieval_modes
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.shared import RegexPattern

from .values import DataType, FieldBound, FieldName, FieldValue, MergeStrategy, PartialDate


@dataclass(frozen=True, slots=True)
class Field:
    """Base field class for entity and relationship types.

    Attributes:
        name: Name of the field.
        data_type: Data type of the field's values.
        description: Description of what the field holds.
        options: Allowed values for the field. Empty if any value is allowed.
        examples: Example values given to the LLM.
        required: Whether instances must have a non-null value for this field.
        merge_strategy: Strategy for merging values when deduplicating instances, or None to use the type's
            default merge strategy.
    """

    name: FieldName
    data_type: DataType
    description: str
    options: tuple[FieldValue, ...]
    examples: tuple[FieldValue, ...]
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
            field_info['options'] = [_to_json(option) for option in self.options]
        if self.examples:
            field_info['examples'] = [_to_json(example) for example in self.examples]
        return json.dumps(field_info)

    def _validate_values(self, default_values: Iterable[FieldValue]) -> None:
        """Validate that options, examples and default values are values the field can hold.

        Extracted strings are stripped and an empty one counts as missing, so a string without that form could never be
        matched or would be stored in a form no extracted value has.

        Args:
            default_values: Default values of the field.

        Raises:
            ValueError: If an option, example or default value isn't of the field's data type, or is a string that is
                empty, has leading or trailing whitespace, or holds a NUL character or a lone surrogate.
        """
        for kind, values in (('Option', self.options), ('Example', self.examples), ('Default value', default_values)):
            for value in values:
                if not self.data_type.accepts(value):
                    raise ValueError(
                        f'Invalid {type(self).__name__} "{self.name}": {kind} {value!r} is not a valid '
                        f'{self.data_type.value} value',
                    )
                if isinstance(value, str) and (not value or value != value.strip()):
                    raise ValueError(
                        f'Invalid {type(self).__name__} "{self.name}": {kind} {value!r} is empty or has leading or '
                        f'trailing whitespace, which extracted values never have',
                    )
                if isinstance(value, str) and any(char == '\x00' or '\ud800' <= char <= '\udfff' for char in value):
                    raise ValueError(
                        f'Invalid {type(self).__name__} "{self.name}": {kind} {value!r} holds a NUL character or a lone '
                        f'surrogate, which extracted values never have',
                    )

    def _validate_merge_strategy(self) -> None:
        """Validate that the field's own merge strategy applies to its data type.

        Raises:
            ValueError: If the merge strategy can't merge values of the field's data type.
        """
        if self.merge_strategy is not None and not self.merge_strategy.supports(self.data_type):
            raise ValueError(
                f'Invalid {type(self).__name__} "{self.name}": Merge strategy "{self.merge_strategy.value}" does not '
                f'apply to {self.data_type.value} values',
            )

    def _validate_bound_types(self, bounds: Iterable[FieldBound]) -> None:
        """Validate that bounds are values of the field's data type.

        Args:
            bounds: Minimum and maximum values of the field.

        Raises:
            ValueError: If a bound isn't of the field's data type.
        """
        for bound in bounds:
            if not self.data_type.accepts(bound):
                raise ValueError(
                    f'Invalid {type(self).__name__} "{self.name}": Bound {bound!r} is not a valid '
                    f'{self.data_type.value} value',
                )

    def _is_valid(
        self, value: Any, regex: RegexPattern | None, minimum: FieldBound | None, maximum: FieldBound | None
    ) -> bool:
        """Check whether a value satisfies the field's data type, options and the given constraints.

        Args:
            value: Value to check.
            regex: Pattern a string value must match, or None if unconstrained.
            minimum: Lowest allowed value, or None if unbounded.
            maximum: Highest allowed value, or None if unbounded.

        Returns:
            True if the value is valid, False otherwise.
        """
        if not self.data_type.accepts(value) or (self.options and value not in self.options):
            return False
        if isinstance(value, str):
            return regex is None or regex.fullmatch(value) is not None
        return _within_bounds(value, minimum, maximum)


@dataclass(frozen=True, slots=True, repr=False)
class EntityField(Field):
    """A field from an entity type.

    Attributes:
        instructions: Extra extraction instructions per context level.
        regex: Pattern that string values must match, per context level.
        minimum: Lowest allowed value, per context level.
        maximum: Highest allowed value, per context level.
        default_value: Default value per context level, used by the ``DEFAULT`` retrieval mode and when an
            extracted value is null.
        retrieval_mode: How the field's value is retrieved, per context level. Levels not listed use ``EXTRACT``.
    """

    instructions: MappingProxyType[ContextLevel, str] = field(compare=False, hash=False)
    regex: MappingProxyType[ContextLevel, RegexPattern] = field(compare=False, hash=False)
    minimum: MappingProxyType[ContextLevel, FieldBound] = field(compare=False, hash=False)
    maximum: MappingProxyType[ContextLevel, FieldBound] = field(compare=False, hash=False)
    default_value: MappingProxyType[ContextLevel, FieldValue] = field(compare=False, hash=False)
    retrieval_mode: MappingProxyType[ContextLevel, EntityRetrievalMode] = field(compare=False, hash=False)

    def __post_init__(self) -> None:
        """Validate entity field invariants.

        Raises:
            ValueError: If the options, constraints, default values, retrieval modes, examples or merge strategy are
                inconsistent with the field rules.
        """
        self._validate_values(self.default_value.values())
        self._validate_constraints()
        self._validate_default_values()
        self._validate_retrieval_mode()
        self._validate_examples()
        self._validate_merge_strategy()

    def is_valid_value(self, value: Any, context_level: ContextLevel) -> bool:
        """Check whether a value satisfies the field's data type, options and constraints at a context level.

        Args:
            value: Value to check.
            context_level: Context level whose regex and bounds apply.

        Returns:
            True if the value is valid, False otherwise.
        """
        return self._is_valid(
            value,
            self.regex.get(context_level),
            self.minimum.get(context_level),
            self.maximum.get(context_level),
        )

    def _validate_constraints(self) -> None:
        """Validate that the constraints apply to the field's data type and are satisfiable.

        Raises:
            ValueError: If a regex is set on a non-string field, bounds are set on a field of a data type without bounds or aren't of its
                data type, or the minimum of a context level is greater than its maximum.
        """
        if self.regex and self.data_type != DataType.STRING:
            raise ValueError(f'Invalid EntityField "{self.name}": regex only applies to string fields')
        if (self.minimum or self.maximum) and not self.data_type.supports_bounds:
            raise ValueError(
                f'Invalid EntityField "{self.name}": min and max only apply to integer, float and date fields',
            )
        self._validate_bound_types((*self.minimum.values(), *self.maximum.values()))
        for ctx_level, minimum in self.minimum.items():
            maximum = self.maximum.get(ctx_level)
            if maximum is not None and minimum > maximum:
                raise ValueError(
                    f'Invalid EntityField "{self.name}": min {minimum} is greater than max {maximum} for context '
                    f'level "{ctx_level.value}"',
                )

    def _validate_default_values(self) -> None:
        """Validate that default values are consistent with field rules.

        Raises:
            ValueError: If a context level uses the ``DEFAULT`` retrieval mode without a default value, or a default
                value is not among the options or doesn't satisfy the regex or bounds for its context level.
        """
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
            if pattern is not None and isinstance(def_val, str) and not pattern.fullmatch(def_val):
                raise ValueError(
                    f'Invalid EntityField "{self.name}": Default value "{def_val}" '
                    f'for context level "{ctx_level.value}" does not match the '
                    f'specified regex pattern: {pattern.pattern}',
                )

            # Bounds must be respected when defined
            minimum, maximum = self.minimum.get(ctx_level), self.maximum.get(ctx_level)
            if not _within_bounds(def_val, minimum, maximum):
                raise ValueError(
                    f'Invalid EntityField "{self.name}": Default value {def_val} for context level '
                    f'"{ctx_level.value}" is {_describe_bounds_violation(minimum, maximum)}',
                )

    def _validate_retrieval_mode(self) -> None:
        """Validate that the retrieval mode is properly defined.

        Raises:
            ValueError: If a retrieval mode is not supported at its context level.
        """
        try:
            ensure_compatible_retrieval_modes(self.retrieval_mode)
        except ValueError as error:
            raise ValueError(f'Invalid EntityField "{self.name}": {error}') from error

    def _validate_examples(self) -> None:
        """Validate that examples are consistent with field rules.

        Raises:
            ValueError: If an example is not among the options or doesn't satisfy the regex or bounds of some context
                level.
        """
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
                if isinstance(example, str) and not pattern.fullmatch(example):
                    raise ValueError(
                        f'Invalid EntityField "{self.name}": Example "{example}" '
                        f'does not match the specified regex pattern for '
                        f'context level "{ctx_level.value}": {pattern.pattern}',
                    )

        # Bounds must be respected when defined
        for ctx_level in ContextLevel:
            minimum, maximum = self.minimum.get(ctx_level), self.maximum.get(ctx_level)
            for example in self.examples:
                if not _within_bounds(example, minimum, maximum):
                    raise ValueError(
                        f'Invalid EntityField "{self.name}": Example {example} for context level '
                        f'"{ctx_level.value}" is {_describe_bounds_violation(minimum, maximum)}',
                    )


@dataclass(frozen=True, slots=True, repr=False)
class RelationshipField(Field):
    """A field from a relationship type.

    Attributes:
        instructions: Extra extraction instructions, or None if there are none.
        regex: Pattern that string values must match, or None if unconstrained.
        minimum: Lowest allowed value, or None if unbounded.
        maximum: Highest allowed value, or None if unbounded.
        default_value: Default value, used by the ``DEFAULT`` retrieval mode and when an extracted value is null.
        retrieval_mode: How the field's value is retrieved.
    """

    instructions: str | None
    regex: RegexPattern | None
    minimum: FieldBound | None
    maximum: FieldBound | None
    default_value: FieldValue | None
    retrieval_mode: RelationshipRetrievalMode

    def __post_init__(self) -> None:
        """Validate relationship field invariants.

        Raises:
            ValueError: If the options, constraints, default value, examples or merge strategy are inconsistent with
                the field rules.
        """
        self._validate_values(() if self.default_value is None else (self.default_value,))
        self._validate_constraints()
        self._validate_default_value()
        self._validate_examples()
        self._validate_merge_strategy()

    def is_valid_value(self, value: Any) -> bool:
        """Check whether a value satisfies the field's data type, options and constraints.

        Args:
            value: Value to check.

        Returns:
            True if the value is valid, False otherwise.
        """
        return self._is_valid(value, self.regex, self.minimum, self.maximum)

    def _validate_constraints(self) -> None:
        """Validate that the constraints apply to the field's data type and are satisfiable.

        Raises:
            ValueError: If a regex is set on a non-string field, bounds are set on a field of a data type without bounds or aren't of its
                data type, or the minimum is greater than the maximum.
        """
        if self.regex is not None and self.data_type != DataType.STRING:
            raise ValueError(f'Invalid RelationshipField "{self.name}": regex only applies to string fields')
        if (self.minimum is not None or self.maximum is not None) and not self.data_type.supports_bounds:
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": min and max only apply to integer, float and date fields',
            )
        self._validate_bound_types(bound for bound in (self.minimum, self.maximum) if bound is not None)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": min {self.minimum} is greater than max {self.maximum}',
            )

    def _validate_default_value(self) -> None:
        """Validate that the default value is consistent with field rules.

        Raises:
            ValueError: If the ``DEFAULT`` retrieval mode has no default value, or the default value is not among the
                options or doesn't satisfy the regex or bounds.
        """
        # For fields that use DEFAULT retrieval mode, a default value must be explicitly defined
        if self.retrieval_mode == RelationshipRetrievalMode.DEFAULT and self.default_value is None:
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": DEFAULT retrieval mode requires an explicit non-null default value',
            )
        if self.default_value is None:
            return

        # Allowed values must be respected when options are defined
        if self.options and self.default_value not in self.options:
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": Default value "{self.default_value}" '
                f"is not present in the field's defined options: {self.options}",
            )

        # Regex pattern must be respected when defined
        if (
            self.regex is not None
            and isinstance(self.default_value, str)
            and not self.regex.fullmatch(self.default_value)
        ):
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": Default value "{self.default_value}" '
                f'does not match the specified regex pattern: {self.regex.pattern}',
            )

        # Bounds must be respected when defined
        if not _within_bounds(self.default_value, self.minimum, self.maximum):
            raise ValueError(
                f'Invalid RelationshipField "{self.name}": Default value {self.default_value} is '
                f'{_describe_bounds_violation(self.minimum, self.maximum)}',
            )

    def _validate_examples(self) -> None:
        """Validate that examples are consistent with field rules.

        Raises:
            ValueError: If an example is not among the options or doesn't satisfy the regex or bounds.
        """
        for example in self.examples:
            # Allowed values must be respected when options are defined
            if self.options and example not in self.options:
                raise ValueError(
                    f'Invalid RelationshipField "{self.name}": Example "{example}" '
                    f"is not present in the field's defined options: {self.options}",
                )

            # Regex pattern must be respected when defined
            if self.regex is not None and isinstance(example, str) and not self.regex.fullmatch(example):
                raise ValueError(
                    f'Invalid RelationshipField "{self.name}": Example "{example}" '
                    f'does not match the specified regex pattern: {self.regex.pattern}',
                )

            # Bounds must be respected when defined
            if not _within_bounds(example, self.minimum, self.maximum):
                raise ValueError(
                    f'Invalid RelationshipField "{self.name}": Example {example} is '
                    f'{_describe_bounds_violation(self.minimum, self.maximum)}',
                )


def _within_bounds(value: FieldValue, minimum: FieldBound | None, maximum: FieldBound | None) -> bool:
    """Check whether a value is within a field's bounds.

    Args:
        value: Value to check. Strings have no bounds.
        minimum: Lowest allowed value, or None if unbounded below.
        maximum: Highest allowed value, or None if unbounded above.

    Returns:
        True if the value is a string or within the bounds, False otherwise.
    """
    if isinstance(value, str):
        return True
    return (minimum is None or value >= minimum) and (maximum is None or value <= maximum)


def _describe_bounds_violation(minimum: FieldBound | None, maximum: FieldBound | None) -> str:
    """Describe the range a value outside a field's bounds should have been in.

    Args:
        minimum: Lowest allowed value, or None if unbounded below.
        maximum: Highest allowed value, or None if unbounded above.

    Returns:
        A phrase completing "<value> is ...".
    """
    if maximum is None:
        return f'less than the min {minimum}'
    if minimum is None:
        return f'greater than the max {maximum}'
    return f'outside the range between the min {minimum} and the max {maximum}'


def _to_json(value: FieldValue) -> str | float | bool:
    """Convert a field value to a JSON value, writing dates in their ISO 8601 form.

    Args:
        value: Field value to convert.

    Returns:
        The ISO 8601 text of a date, otherwise the same value.
    """
    return str(value) if isinstance(value, PartialDate) else value
