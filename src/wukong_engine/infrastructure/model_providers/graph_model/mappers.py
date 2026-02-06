from types import MappingProxyType
from typing import Any

from wukong_engine.core.graph.model import EntityType, Field, GraphModel
from wukong_engine.core.graph.model.values import EntityTypeName, FieldName, RegexPattern

from .schemas import EntityTypeSchema, FieldSchema, GraphModelSchema


def schema_to_graph_model(schema: GraphModelSchema) -> GraphModel:
    """Convert a GraphModelSchema to a GraphModel domain model."""
    return GraphModel(
        entity_types=tuple(_schema_to_entity_type(name, schema) for name, schema in schema.entity_types.items()),
    )


def _schema_to_entity_type(name: str, schema: EntityTypeSchema) -> EntityType:
    """Convert an EntityTypeSchema to an EntityType domain model."""
    return EntityType(
        name=EntityTypeName(name),
        document_groups=MappingProxyType({k: tuple(_as_list(v)) for k, v in schema.document_groups.items()}),
        fields=tuple(_schema_to_field(name, schema) for name, schema in schema.fields.items()),
    )


def _schema_to_field(name: str, schema: FieldSchema) -> Field:
    """Convert a FieldSchema to a Field domain model."""
    return Field(
        name=FieldName(name),
        data_type=schema.data_type,
        description=schema.description,
        instructions=MappingProxyType(_as_dict(schema.instructions)),
        options=frozenset(_as_list(schema.options)),
        examples=tuple(_as_list(schema.examples)),
        regex=MappingProxyType({k: RegexPattern(v) for k, v in _as_dict(schema.regex).items()}),
        default_value=MappingProxyType(_as_dict(schema.default_value)),
        retrieval_mode=MappingProxyType(_as_dict(schema.retrieval_mode)),
        required=schema.required,
    )


def _as_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f'Mapping Error: expected a dictionary, got {type(value)} instead')
    return value


def _as_list(value: Any) -> list:
    if not isinstance(value, list):
        raise TypeError(f'Mapping Error: expected a list, got {type(value)} instead')
    return value
