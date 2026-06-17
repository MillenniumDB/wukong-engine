"""Result materializers for extraction tasks."""

from typing import Any

from wukong_engine.app.data_extraction.models import ExtractionResult
from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.model import EntityType, GraphModel
from wukong_engine.core.graph.model.values import EntityTypeName


class EntityMaterializer:
    """Materializer that converts raw extraction results into entity instances."""

    def __init__(self, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies."""
        self._pk_normalizer = pk_normalizer

    def materialize(self, result: ExtractionResult, model: GraphModel) -> tuple[Entity, ...]:
        """Materialize the extraction result into entity instances."""
        context_level = result.job.task.context_level
        extracted_entities = result.data.get('entities', [])
        materialized_entities: list[Entity] = []
        for extracted in extracted_entities:
            # Get entity type
            entity_type = self._materialize_entity_type(extracted, model)
            if entity_type is None:
                continue

            # Assemble properties
            properties: dict[str, Any] = {}

            # Add constant properties
            properties.update(
                self._materialize_properties(extracted, entity_type, context_level, EntityRetrievalMode.DEFAULT),
            )

            # Add extracted properties
            properties.update(
                self._materialize_properties(extracted, entity_type, context_level, EntityRetrievalMode.EXTRACT),
            )

            # Validate properties and skip materialization if invalid
            if not self._are_valid_properties(properties, entity_type, context_level):
                continue

            # Normalize PK value and skip materialization if invalid
            normalized_pk = self._pk_normalizer.normalize(properties[entity_type.primary_key.value])
            if normalized_pk is None:
                continue

            # Materialize full entity instance
            entity = Entity.from_extraction(entity_type=entity_type, properties=properties, normalized_pk=normalized_pk)
            materialized_entities.append(entity)

        return tuple(materialized_entities)

    def _materialize_entity_type(self, data: dict[str, Any], model: GraphModel) -> EntityType | None:
        """Materialize the entity type from extracted data."""
        try:
            extracted_et_name = data.get('_entity_type')
            if extracted_et_name is None:  # Missing entity type in extracted data
                return None
            et_name = EntityTypeName(str(extracted_et_name))
            entity_type = model.entity_type(et_name)
            if entity_type is not None:  # Valid entity type found in graph model
                return entity_type
        except ValueError:
            return None  # Invalid entity type name in extracted data

    def _materialize_properties(
        self,
        data: dict[str, Any],
        entity_type: EntityType,
        context_level: ContextLevel,
        retrieval_mode: EntityRetrievalMode,
    ) -> dict[str, Any]:
        """Materialize the entity properties obtained through a given retrieval mode."""
        # Skipped fields should not be materialized
        if retrieval_mode == EntityRetrievalMode.SKIP:
            return {}

        # Materialize properties according to the retrieval mode
        properties: dict[str, Any] = {}
        for field in entity_type.fields_for(context_level, retrieval_mode):
            value = None

            # For extracted fields, assign the extracted value when it exists in the data
            if retrieval_mode == EntityRetrievalMode.EXTRACT:
                value = data.get(field.name.value)

            # Assign default value when it corresponds to a constant field or when the extracted value is null
            value = str(value) if value is not None else field.default_value.get(context_level)

            # If the assigned value is not null, add it to the materialized properties
            if value is not None:
                properties[field.name.value] = value

        return properties

    def _are_valid_properties(
        self,
        properties: dict[str, Any],
        entity_type: EntityType,
        context_level: ContextLevel,
    ) -> bool:
        """Check whether the materialized properties are valid according to the entity type definition."""
        for field in entity_type.fields_for(context_level, EntityRetrievalMode.EXTRACT):
            value = properties.get(field.name.value)

            # Required fields must be present and not null
            if field.required and value is None:
                return False

            # Allowed values must be respected when options are defined
            if field.options and value is not None and value not in field.options:
                return False

            # Regex pattern must be respected when defined
            regex_pattern = field.regex.get(context_level)
            if regex_pattern is not None and value is not None and not regex_pattern.match(str(value)):
                return False

        return True
