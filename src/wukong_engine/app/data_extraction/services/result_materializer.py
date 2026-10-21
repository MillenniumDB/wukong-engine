"""Result materializers for extraction tasks."""

from typing import Any, Protocol

from wukong_engine.app.data_extraction.elements import (
    ExtractionJob,
    ExtractionResult,
    RelationshipExtractionRequestObjects,
)
from wukong_engine.app.data_extraction.exceptions import ExtractionResultError
from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.knowledge.elements import Entity, EntityRef, Relationship
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model import EntityType, KnowledgeModel, RelationshipType
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.core.shared.regex_pattern import RegexPattern

from .repository import EntityExtractionRepository, RelationshipExtractionRepository


def _extracted_items(data: Any, key: str) -> list[dict[str, Any]]:
    """Get the extracted items of a result, skipping those that aren't objects.

    Args:
        data: Data parsed from the LLM response.
        key: Key of the response holding the list of extracted items.

    Returns:
        The extracted items that are objects.

    Raises:
        ExtractionResultError: If the data is not an object holding a list under the key.
    """
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ExtractionResultError(f'Malformed extraction result, expected an object with a "{key}" list')
    return [item for item in items if isinstance(item, dict)]


def _is_valid_value(value: str, options: tuple[str, ...], regex: RegexPattern | None) -> bool:
    """Check whether a field value satisfies the field's constraints.

    Args:
        value: Materialized field value.
        options: Allowed values of the field. Empty if any value is allowed.
        regex: Pattern the value must match, or None if unconstrained.

    Returns:
        True if the value is one of the options (if any) and matches the regex (if any), False otherwise.
    """
    if options and value not in options:
        return False
    return regex is None or regex.match(value) is not None


class ExtractionResultMaterializer(Protocol):
    """Materializer that converts raw extraction results into knowledge object instances."""

    def materialize(self, result: ExtractionResult, job: ExtractionJob, model: KnowledgeModel) -> tuple[object, ...]:
        """Materialize the extraction result into knowledge object instances.

        Extracted items that are malformed or don't match the knowledge model are skipped.

        Args:
            result: Raw LLM extraction result to materialize.
            job: Extraction job that produced the result.
            model: Knowledge model used to resolve and validate types and fields.

        Returns:
            The valid knowledge objects built from the result.

        Raises:
            ExtractionResultError: If the result as a whole doesn't have the structure of the expected response.
        """
        ...


class EntityExtractionResultMaterializer(ExtractionResultMaterializer):
    """Materializer that converts raw extraction results into entity instances."""

    def __init__(self, repository: EntityExtractionRepository, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies.

        Args:
            repository: Repository used to look up the entity types assigned to a job.
            pk_normalizer: Normalizer applied to primary key values before computing entity identities.
        """
        self._repository = repository
        self._pk_normalizer = pk_normalizer

    def materialize(self, result: ExtractionResult, job: ExtractionJob, model: KnowledgeModel) -> tuple[Entity, ...]:
        """Materialize the extraction result into entity instances.

        Items under the result's ``entities`` key are skipped when their type is unknown or not assigned to the job,
        a required field is missing or invalid, or their primary key doesn't normalize. Invalid values of optional
        fields are discarded instead, as if they had not been extracted.

        Args:
            result: Raw LLM extraction result to materialize.
            job: Extraction job that produced the result.
            model: Knowledge model used to resolve and validate entity types and fields.

        Returns:
            The valid entities built from the result.
        """
        extracted_entities = _extracted_items(result.data, 'entities')
        job_types = set(self._repository.get_job_entity_types(job))
        materialized_entities: list[Entity] = []
        for extracted in extracted_entities:
            # Get entity type
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
        model: KnowledgeModel,
    ) -> EntityType | None:
        """Materialize the entity type from extracted data.

        Args:
            data: Single extracted item, carrying its type name under ``_entity_type``.
            job_types: Entity types assigned to the job that produced the item.
            model: Knowledge model used to resolve the type name.

        Returns:
            The entity type, or None if it is missing, invalid, unknown to the model, or not assigned to the job.
        """
        try:
            extracted_et_name = data.get('_entity_type')

            # Missing entity type in extracted data
            if extracted_et_name is None:
                return None

            # Get EntityType instance from knowledge model
            et_name = EntityTypeName(str(extracted_et_name))
            entity_type = model.entity_type(et_name)

            # Valid entity type found in knowledge model and job types
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
        """Materialize the entity properties obtained through a given retrieval mode.

        Extracted values are stringified, and those of optional fields that don't satisfy the field's options or regex
        are discarded; fields with no (valid) extracted value fall back to their default for the context level, and
        fields that end up null are omitted.

        Args:
            data: Single extracted item holding the extracted field values.
            entity_type: Entity type whose fields are materialized.
            context_level: Context level of the job, which selects the applicable fields and defaults.
            retrieval_mode: Retrieval mode of the fields to materialize.

        Returns:
            Mapping from field name to value. Empty for the ``SKIP`` retrieval mode.
        """
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

            # Discard an invalid optional value (an invalid required one is left for validation to reject the entity)
            regex = field.regex.get(context_level)
            if value is not None and not field.required and not _is_valid_value(str(value), field.options, regex):
                value = None

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
        """Check whether the materialized properties are valid according to the entity type definition.

        Only extracted fields are checked, against their required flag, allowed options, and regex.

        Args:
            properties: Materialized properties to validate.
            entity_type: Entity type defining the field constraints.
            context_level: Context level of the job, which selects the applicable fields and regexes.

        Returns:
            True if every extracted field satisfies its constraints, False otherwise.
        """
        for field in entity_type.fields_for(context_level, EntityRetrievalMode.EXTRACT):
            value = properties.get(field.name.value)

            # Required fields must be present and not null
            if field.required and value is None:
                return False

            # Allowed values and regex pattern must be respected when defined
            if value is not None and not _is_valid_value(str(value), field.options, field.regex.get(context_level)):
                return False

        return True


class RelationshipExtractionResultMaterializer(ExtractionResultMaterializer):
    """Materializer that converts raw extraction results into relationship instances."""

    def __init__(self, repository: RelationshipExtractionRepository, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies.

        Args:
            repository: Repository used to look up a job's relationship types and resolve its entity references.
            pk_normalizer: Normalizer applied to primary key values when the relationship identity requires one.
        """
        self._repository = repository
        self._pk_normalizer = pk_normalizer

    def materialize(
        self, result: ExtractionResult, job: ExtractionJob, model: KnowledgeModel
    ) -> tuple[Relationship, ...]:
        """Materialize the extraction result into relationship instances.

        Items under the result's ``relationships`` key are skipped when their type is unknown or not assigned to the
        job, their endpoints don't resolve to a valid endpoint of the type, a required field is missing or invalid,
        or a required primary key is missing or doesn't normalize. Invalid values of optional fields are discarded
        instead, as if they had not been extracted.

        Args:
            result: Raw LLM extraction result to materialize.
            job: Extraction job that produced the result.
            model: Knowledge model used to resolve and validate relationship types, fields, and endpoints.

        Returns:
            The valid relationships built from the result.
        """
        extracted_relationships = _extracted_items(result.data, 'relationships')
        if not extracted_relationships:
            return ()

        # Load the job's context, which is the same for every extracted relationship
        job_types = set(self._repository.get_job_relationship_types(job))
        entity_refs = self._repository.get_job_entity_ref_mapping(job)
        entity_context_levels = self._entity_context_levels(self._repository.get_job_extraction_elements(job, model))

        materialized_relationships: list[Relationship] = []
        for extracted in extracted_relationships:
            # Get relationship type
            relationship_type = self._materialize_relationship_type(extracted, job_types, model)
            if relationship_type is None:
                continue

            # Get source and target entity IDs
            endpoint = self._materialize_endpoint(extracted, relationship_type, entity_refs, entity_context_levels)
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
        model: KnowledgeModel,
    ) -> RelationshipType | None:
        """Materialize the relationship type from extracted data.

        Args:
            data: Single extracted item, carrying its type name under ``_relationship_type``.
            job_types: Relationship types assigned to the job that produced the item.
            model: Knowledge model used to resolve the type name.

        Returns:
            The relationship type, or None if it is missing, invalid, unknown to the model, or not assigned to the
            job.
        """
        try:
            extracted_rt_name = data.get('_relationship_type')

            # Missing relationship type in extracted data
            if extracted_rt_name is None:
                return None

            # Get RelationshipType instance from knowledge model
            rt_name = RelationshipTypeName(str(extracted_rt_name))
            relationship_type = model.relationship_type(rt_name)

            # Valid relationship type found in knowledge model and job types
            if relationship_type is not None and relationship_type.name in job_types:
                return relationship_type
        except ValueError:
            return None  # Invalid relationship type name in extracted data

    @staticmethod
    def _entity_context_levels(elements: RelationshipExtractionRequestObjects) -> dict[EntityId, set[ContextLevel]]:
        """Map each entity available to a job to the context levels it is available at.

        Args:
            elements: Extraction elements of the job, with its chunk and parent document entities.

        Returns:
            The context levels (chunk and/or parent document) of each entity available to the job.
        """
        context_levels: dict[EntityId, set[ContextLevel]] = {}
        for entity in elements.chunk_entities:
            context_levels.setdefault(entity.id, set()).add(ContextLevel.CHUNK)
        for entity in elements.parent_document_entities:
            context_levels.setdefault(entity.id, set()).add(ContextLevel.DOCUMENT)
        return context_levels

    @staticmethod
    def _materialize_endpoint(
        data: dict[str, Any],
        relationship_type: RelationshipType,
        entity_refs: dict[str, EntityRef],
        entity_context_levels: dict[EntityId, set[ContextLevel]],
    ) -> tuple[EntityId, EntityId] | None:
        """Materialize the source and target entity IDs.

        The extracted ``_source_entity_id`` and ``_target_entity_id`` are temporary IDs local to the job's prompt;
        they are capitalized and mapped back to the job's entity references.

        Args:
            data: Single extracted item holding the temporary source and target IDs.
            relationship_type: Relationship type whose endpoint definitions the pair must match.
            entity_refs: Mapping from the temporary entity IDs of the job's prompt to their entity references.
            entity_context_levels: Context levels of each entity available to the job.

        Returns:
            The source and target entity IDs, or None if either ID is missing or unknown, or the pair doesn't match
            an endpoint of the relationship type.
        """
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
        source_ref = entity_refs.get(source_id)
        target_ref = entity_refs.get(target_id)

        # Invalid EntityRef instances
        if source_ref is None or target_ref is None:
            return None

        # Get context levels for source and target refs
        source_ctx = entity_context_levels.get(source_ref.entity_id, set())
        target_ctx = entity_context_levels.get(target_ref.entity_id, set())

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
        """Materialize the relationship properties obtained through a given retrieval mode.

        Extracted values are stringified, and those of optional fields that don't satisfy the field's options or regex
        are discarded; fields with no (valid) extracted value fall back to their default, and fields that end up null
        are omitted.

        Args:
            data: Single extracted item holding the extracted field values.
            relationship_type: Relationship type whose fields are materialized.
            retrieval_mode: Retrieval mode of the fields to materialize.

        Returns:
            Mapping from field name to value.
        """
        # Materialize properties according to the retrieval mode
        properties: dict[str, Any] = {}
        for field in relationship_type.fields_for(retrieval_mode):
            value = None

            # For extracted fields, assign the extracted value when it exists in the data
            if retrieval_mode == RelationshipRetrievalMode.EXTRACT:
                value = data.get(field.name.value)

            # Discard an invalid optional value (an invalid required one is left for validation to reject the item)
            if value is not None and not field.required and not _is_valid_value(str(value), field.options, field.regex):
                value = None

            # Assign default value when it corresponds to a constant field or when the extracted value is null
            value = str(value) if value is not None else field.default_value

            # If the assigned value is not null, add it to the materialized properties
            if value is not None:
                properties[field.name.value] = value

        return properties

    def _are_valid_properties(self, properties: dict[str, Any], relationship_type: RelationshipType) -> bool:
        """Check whether the materialized properties are valid according to the relationship type definition.

        Only extracted fields are checked, against their required flag, allowed options, and regex.

        Args:
            properties: Materialized properties to validate.
            relationship_type: Relationship type defining the field constraints.

        Returns:
            True if every extracted field satisfies its constraints, False otherwise.
        """
        for field in relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT):
            value = properties.get(field.name.value)

            # Required fields must be present and not null
            if field.required and value is None:
                return False

            # Allowed values and regex pattern must be respected when defined
            if value is not None and not _is_valid_value(str(value), field.options, field.regex):
                return False

        return True
