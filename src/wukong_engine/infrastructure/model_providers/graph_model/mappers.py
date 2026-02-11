from types import MappingProxyType
from typing import Any

from wukong_engine.core.graph.model import EntityType, ExtractionConfig, Field, GraphModel, RelationshipType
from wukong_engine.core.graph.model.values import EntityTypeName, FieldName, RegexPattern, RelationshipTypeName

from .schemas import EntityTypeSchema, ExtractionSchema, FieldSchema, GraphModelSchema, RelationshipTypeSchema


def schema_to_graph_model(schema: GraphModelSchema) -> GraphModel:
    """Convert a GraphModelSchema to a GraphModel domain model."""
    return GraphModel(
        extraction_config=_schema_to_extraction_config(schema.extraction),
        entity_types=MappingProxyType(
            {EntityTypeName(name): _schema_to_entity_type(schema) for name, schema in schema.entity_types.items()},
        ),
        relationship_types=MappingProxyType(
            {
                RelationshipTypeName(name): _schema_to_relationship_type(schema)
                for name, schema in schema.relationship_types.items()
            },
        ),
    )


def _schema_to_extraction_config(schema: ExtractionSchema) -> ExtractionConfig:
    """Convert an ExtractionSchema to an ExtractionConfig domain model."""
    return ExtractionConfig(
        llm_persona=schema.llm.persona,
        document_context=schema.llm.document_context,
        input_language=schema.language.input,
        output_language=schema.language.output,
        entity_projection=frozenset(EntityTypeName(name) for name in schema.projection.enabled_entities)
        if schema.projection.enabled_entities is not None
        else None,
        relationship_projection=frozenset(
            RelationshipTypeName(name) for name in schema.projection.enabled_relationships
        )
        if schema.projection.enabled_relationships is not None
        else None,
    )


def _schema_to_entity_type(schema: EntityTypeSchema) -> EntityType:
    """Convert an EntityTypeSchema to an EntityType domain model."""
    return EntityType(
        description=schema.description,
        instructions=MappingProxyType(_as_dict(schema.instructions)),
        primary_key=FieldName(schema.primary_key),
        fields=MappingProxyType({FieldName(name): _schema_to_field(schema) for name, schema in schema.fields.items()}),
        document_groups=MappingProxyType({k: frozenset(_as_set(v)) for k, v in schema.document_groups.items()}),
        deduplication_mode=schema.deduplication,
    )


def _schema_to_relationship_type(schema: RelationshipTypeSchema) -> RelationshipType:
    """Convert a RelationshipTypeSchema to a RelationshipType domain model."""
    return RelationshipType(
        description=schema.description,
        instructions=MappingProxyType(_as_dict(schema.instructions)),
        primary_key=FieldName(schema.primary_key),
        fields=MappingProxyType({FieldName(name): _schema_to_field(schema) for name, schema in schema.fields.items()}),
        deduplication_mode=schema.deduplication,
    )


def _schema_to_field(schema: FieldSchema) -> Field:
    """Convert a FieldSchema to a Field domain model."""
    return Field(
        data_type=schema.data_type,
        description=schema.description,
        instructions=MappingProxyType(_as_dict(schema.instructions)),
        options=tuple(_as_list(schema.options)),
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


def _as_set(value: Any) -> set:
    if not isinstance(value, set):
        raise TypeError(f'Mapping Error: expected a set, got {type(value)} instead')
    return value
