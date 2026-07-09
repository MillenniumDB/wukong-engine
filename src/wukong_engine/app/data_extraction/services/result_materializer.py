"""Result materializers for extraction tasks."""

from typing import Any, Protocol

from wukong_engine.app.data_extraction.elements import ExtractionJob, ExtractionResult
from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.graph.elements import Entity, Relationship
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model import EntityType, GraphModel, RelationshipType
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipTypeName

from .repository import EntityExtractionRepository, RelationshipExtractionRepository


class ExtractionResultMaterializer(Protocol):
    """Materializer that converts raw extraction results into graph object instances."""

    def materialize(self, result: ExtractionResult, job: ExtractionJob, model: GraphModel) -> tuple[object, ...]:
        """Materialize the extraction result into graph object instances."""
        ...


class EntityExtractionResultMaterializer(ExtractionResultMaterializer):
    """Materializer that converts raw extraction results into entity instances."""

    def __init__(self, repository: EntityExtractionRepository, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies."""
        self._repository = repository
        self._pk_normalizer = pk_normalizer

    def materialize(self, result: ExtractionResult, job: ExtractionJob, model: GraphModel) -> tuple[Entity, ...]:
        """Materialize the extraction result into entity instances."""
        extracted_entities = result.data.get('entities', [])
        materialized_entities: list[Entity] = []
        for extracted in extracted_entities:
            # Get entity type
            job_types = set(self._repository.get_job_entity_types(job))
            entity_type = self._materialize_entity_type(extracted, job_types, model)
            if entity_type is None:
                continue

            # Assemble properties
            properties: dict[str, Any] = {}

            # Add constant properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    entity_type,
                    job.context_ref.level,
                    EntityRetrievalMode.DEFAULT,
                ),
            )

            # Add extracted properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    entity_type,
                    job.context_ref.level,
                    EntityRetrievalMode.EXTRACT,
                ),
            )

            # Validate properties and skip materialization if invalid
            if not self._are_valid_properties(properties, entity_type, job.context_ref.level):
                continue

            # Normalize PK value and skip materialization if invalid
            normalized_pk = self._pk_normalizer.normalize(properties[entity_type.primary_key.value])
            if normalized_pk is None:
                continue  # Invalid primary key value

            # Materialize full entity instance
            entity = Entity.from_extraction(entity_type, properties, normalized_pk)
            materialized_entities.append(entity)

        return tuple(materialized_entities)

    def _materialize_entity_type(
        self,
        data: dict[str, Any],
        job_types: set[EntityTypeName],
        model: GraphModel,
    ) -> EntityType | None:
        """Materialize the entity type from extracted data."""
        try:
            extracted_et_name = data.get('_entity_type')

            # Missing entity type in extracted data
            if extracted_et_name is None:
                return None

            # Get EntityType instance from graph model
            et_name = EntityTypeName(str(extracted_et_name))
            entity_type = model.entity_type(et_name)

            # Valid entity type found in graph model and job types
            if entity_type is not None and entity_type.name in job_types:
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


class RelationshipExtractionResultMaterializer(ExtractionResultMaterializer):
    """Materializer that converts raw extraction results into relationship instances."""

    def __init__(self, repository: RelationshipExtractionRepository, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies."""
        self._repository = repository
        self._pk_normalizer = pk_normalizer

    def materialize(self, result: ExtractionResult, job: ExtractionJob, model: GraphModel) -> tuple[Relationship, ...]:
        """Materialize the extraction result into relationship instances."""
        extracted_relationships = result.data.get('relationships', [])
        materialized_relationships: list[Relationship] = []
        for extracted in extracted_relationships:
            # Get relationship type
            job_types = set(self._repository.get_job_relationship_types(job))
            relationship_type = self._materialize_relationship_type(extracted, job_types, model)
            if relationship_type is None:
                continue

            # Get source and target entity IDs
            endpoint = self._materialize_endpoint(extracted, relationship_type, job, model)
            if endpoint is None:
                continue
            source, target = endpoint

            # Assemble properties
            properties: dict[str, Any] = {}

            # Add constant properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    relationship_type,
                    RelationshipRetrievalMode.DEFAULT,
                ),
            )

            # Add extracted properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    relationship_type,
                    RelationshipRetrievalMode.EXTRACT,
                ),
            )

            # Validate properties and skip materialization if invalid
            if not self._are_valid_properties(properties, relationship_type):
                continue

            # If the identity policy uses a Primary Key, normalize the PK value and skip materialization if invalid
            normalized_pk = None
            if relationship_type.identity_policy.requires_primary_key:
                pk_field = relationship_type.primary_key
                if pk_field is None or pk_field.value not in properties:
                    continue  # No valid primary key field
                normalized_pk = self._pk_normalizer.normalize(properties[pk_field.value])
                if normalized_pk is None:
                    continue  # Invalid primary key value

            # Materialize full relationship instance
            relationship = Relationship.from_extraction(relationship_type, source, target, properties, normalized_pk)
            materialized_relationships.append(relationship)

        return tuple(materialized_relationships)

    def _materialize_relationship_type(
        self,
        data: dict[str, Any],
        job_types: set[RelationshipTypeName],
        model: GraphModel,
    ) -> RelationshipType | None:
        """Materialize the relationship type from extracted data."""
        try:
            extracted_rt_name = data.get('_relationship_type')

            # Missing relationship type in extracted data
            if extracted_rt_name is None:
                return None

            # Get RelationshipType instance from graph model
            rt_name = RelationshipTypeName(str(extracted_rt_name))
            relationship_type = model.relationship_type(rt_name)

            # Valid relationship type found in graph model and job types
            if relationship_type is not None and relationship_type.name in job_types:
                return relationship_type
        except ValueError:
            return None  # Invalid relationship type name in extracted data

    def _materialize_endpoint(
        self,
        data: dict[str, Any],
        relationship_type: RelationshipType,
        job: ExtractionJob,
        model: GraphModel,
    ) -> tuple[EntityId, EntityId] | None:
        """Materialize the source and target entity IDs."""
        # Get source and target temporary entity IDs from extracted data
        source_id = data.get('_source_entity_id')
        target_id = data.get('_target_entity_id')

        # Missing temporary entity IDs in extracted data
        if source_id is None or target_id is None:
            return None

        # Normalize temporary entity IDs
        source_id = str(source_id).capitalize()
        target_id = str(target_id).capitalize()

        # Map the temporary IDs back to EntityRef instances
        source_ref = self._repository.get_entity_ref_for_job(job, source_id)
        target_ref = self._repository.get_entity_ref_for_job(job, target_id)

        # Invalid EntityRef instances
        if source_ref is None or target_ref is None:
            return None

        # Get context levels for source and target refs
        source_ctx = self._repository.get_job_entity_ref_context_levels(job, source_ref, model)
        target_ctx = self._repository.get_job_entity_ref_context_levels(job, target_ref, model)

        # Endpoint references do not match any endpoint defined in the relationship type
        if not relationship_type.is_valid_endpoint(
            source_ref.entity_type_name,
            source_ctx,
            target_ref.entity_type_name,
            target_ctx,
        ):
            return None

        # Return valid endpoint
        return source_ref.entity_id, target_ref.entity_id

    def _materialize_properties(
        self,
        data: dict[str, Any],
        relationship_type: RelationshipType,
        retrieval_mode: RelationshipRetrievalMode,
    ) -> dict[str, Any]:
        """Materialize the relationship properties obtained through a given retrieval mode."""
        # Materialize properties according to the retrieval mode
        properties: dict[str, Any] = {}
        for field in relationship_type.fields_for(retrieval_mode):
            value = None

            # For extracted fields, assign the extracted value when it exists in the data
            if retrieval_mode == RelationshipRetrievalMode.EXTRACT:
                value = data.get(field.name.value)

            # Assign default value when it corresponds to a constant field or when the extracted value is null
            value = str(value) if value is not None else field.default_value

            # If the assigned value is not null, add it to the materialized properties
            if value is not None:
                properties[field.name.value] = value

        return properties

    def _are_valid_properties(self, properties: dict[str, Any], relationship_type: RelationshipType) -> bool:
        """Check whether the materialized properties are valid according to the relationship type definition."""
        for field in relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT):
            value = properties.get(field.name.value)

            # Required fields must be present and not null
            if field.required and value is None:
                return False

            # Allowed values must be respected when options are defined
            if field.options and value is not None and value not in field.options:
                return False

            # Regex pattern must be respected when defined
            regex_pattern = field.regex
            if regex_pattern is not None and value is not None and not regex_pattern.match(str(value)):
                return False

        return True
