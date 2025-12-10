from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from wukong_engine.core.enums import DataType, FieldMode, Source


class FieldSchema(BaseModel):
    """Schema-level representation of a field definition."""

    data_type: DataType
    description: str | None = None
    instructions: dict[Source, str] | None = None
    options: list[str] | None = None
    regex: dict[Source, str] | None = None
    examples: list[str] | None = None
    mode: dict[Source, FieldMode]
    default_value: dict[Source, str] | None = None
    required: bool = False

    # ----------------------------
    # Validators
    # ----------------------------

    @field_validator('data_type', mode='before')
    @classmethod
    def parse_data_type(cls, v: Any) -> DataType:
        if isinstance(v, DataType):
            return v
        if isinstance(v, str):
            return DataType.from_string(v)
        raise TypeError('Invalid data_type')

    @field_validator(
        'instructions',
        'regex',
        'default_value',
        mode='before',
    )
    @classmethod
    def parse_source_dicts(cls, v: Any):
        if v is None:
            return None
        return _normalize_source_dict(v)

    @field_validator('mode', mode='before')
    @classmethod
    def parse_mode(cls, v: Any) -> dict[Source, FieldMode]:
        if isinstance(v, str):
            return {
                Source.CHUNK: FieldMode.from_string(v),
                Source.DOCUMENT: FieldMode.from_string(v),
            }

        if isinstance(v, dict):
            return {Source.from_string(k): FieldMode.from_string(val) for k, val in v.items()}

        raise TypeError('Invalid mode')

    @field_validator('options', 'examples', mode='before')
    @classmethod
    def parse_string_or_list(cls, v: Any):
        if v is None:
            return None
        return _normalize_string_or_list(v)


def _normalize_source_dict(
    value: str | dict[str, str],
) -> dict[Source, str]:
    """Normalize either:
      - a single string
      - or a dict with keys like 'chunk', 'document'

    into Dict[Source, str].
    """
    if isinstance(value, str):
        return {
            Source.CHUNK: value,
            Source.DOCUMENT: value,
        }

    if isinstance(value, dict):
        return {Source.from_string(k): v for k, v in value.items()}

    raise TypeError('Invalid source-based value')


def _normalize_string_or_list(
    value: str | list[str],
) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    raise TypeError('Expected string or list of strings')
